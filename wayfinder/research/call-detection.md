# Как заметить, что чужое приложение открыло микрофон

Тикет: `../01-call-detection.md`. Проверено на этой машине 2026-11-03: `pactl info` → `Server Name: PulseAudio (on PipeWire 1.0.5)`, `pw-cli --version` → `libpipewire 1.0.5`.

## 1. События: `pactl subscribe`

`pactl subscribe` «Subscribe to events, pactl does not exit by itself, but keeps waiting for new events» (https://manpages.debian.org/bookworm/pulseaudio-utils/pactl.1.en.html). Событие несёт только тип и индекс, свойства надо дочитывать через `pactl -f json list source-outputs`.

Опыт: `timeout 5 pactl subscribe` и параллельно `timeout 2 pw-record -P '{ application.name=meetrec media.role=Production }' t.wav`:

```
Event 'new' on client #1198
Event 'new' on source-output #1199
Event 'change' on source-output #1199   (x3)
Event 'change' on source #54
Event 'change' on card #45
Event 'change' on source-output #1199
Event 'new' on client #1206             <- наши же pactl list / pw-dump
Event 'remove' on client #1206
...
Event 'remove' on source-output #1199
Event 'remove' on client #1198
Event 'change' on source #54
```

Открытие потока записи = `Event 'new' on source-output #N`, закрытие = `Event 'remove' on source-output #N`. Native-клиенты PipeWire (`pw-record`) видны через pipewire-pulse так же, как pulse-клиенты.

Ловушка локали: без `LC_ALL=C` вывод переведён (`Событие «появление» в отношении выхода источника №1188`), а `pactl -f json list source-outputs` в локали ru_RU упал с `Invalid non-ASCII character: 0xffffffd0`. Запускать оба с `LC_ALL=C`.

## 2. Альтернатива: `pw-dump -m`

`pw-dump -m -N` (`-m, --monitor  monitor changes`) пишет JSON-массивы изменений. Опыт с `pw-record -P '{ application.name=meetrec }'`: появляется `PipeWire:Interface:Node` с `media.class = "Stream/Input/Audio"`, `state` идёт `suspended` → `running`; удаление выглядит как `{"id":76,"info":null}`, без свойств, поэтому демону надо помнить `id → props`. Свойства процесса (`application.process.binary`, `application.process.id`) у native-клиента лежат на объекте `PipeWire:Interface:Client`, а не на ноде (см. п. 3). Работает, но разбирать сложнее, чем `pactl`.

## 3. Какие свойства несёт source-output

`pw-record` (native PipeWire), `LC_ALL=C pactl list source-outputs`:

```
application.name = "meetrec"          <- из -P; без -P: "pw-record"
node.name = "pw-record"
media.role = "production"             <- без -P: "music" (pw-record --help: "--media-role ... (default Music)")
media.class = "Stream/Input/Audio"
```

`application.process.binary` и `application.process.id` в свойствах потока нет. Они есть только у клиента в `pw-dump`: `"application.name": "pw-cat"`, `"application.process.binary": "pw-cat"`, `"application.process.id": 724975`.

`parecord` (pulse-клиент, как Chrome, Firefox и Zoom), `pactl -f json list source-outputs`:

```
"client.api": "pipewire-pulse",
"application.name": "parecord",
"application.process.id": "725631",
"application.process.binary": "pacat",
"node.name": "parecord",
"media.class": "Stream/Input/Audio"
```

У pulse-клиентов pipewire-pulse копирует свойства процесса в поток, так что `application.process.binary` доступен прямо в `list source-outputs`. `media.role` не задан.

По приложениям, из их исходников и логов:

- Chromium/Chrome: контекст `pa_context_new(..., PRODUCT_STRING " input")` / `PRODUCT_STRING`, поток `pa_stream_new_with_proplist(context, "RecordStream", ...)`, из свойств ставится только `PA_PROP_APPLICATION_ICON_NAME`, `media.role` не ставится (https://github.com/chromium/chromium/blob/main/media/audio/pulse/pulse_util.cc). Значит `application.name` = «Chromium» или «Google Chrome», `media.name` = `RecordStream`.
- Firefox (cubeb): `pa_context_new(..., ctx->context_name)` и `pa_stream_new(..., stream_name, ...)` без proplist, `media.role` тоже нет (https://github.com/mozilla/cubeb/blob/master/src/cubeb_pulse.c).
- Zoom desktop: в `pacmd list-sink-inputs` `client: 51 <ZOOM VoiceEngine>`, `application.name = "ZOOM VoiceEngine"`, `application.process.binary = "zoom"` (https://bbs.archlinux.org/viewtopic.php?id=255994). Это поток воспроизведения, для записи, скорее всего, то же имя клиента. Не проверено.

Вывод: `media.role` для распознавания бесполезен (браузеры его не ставят). Различать приложения по `application.process.binary`, а в журнал писать `application.name`.

## 4. Как исключить собственные потоки

- Свой `pw-record` запускать с `-P '{ application.name=meetrec }'` (`pw-record --help`: `-P --properties  Set node properties`). Проверено: `application.name = "meetrec"` виден в `pactl list source-outputs`. PID собственного процесса в свойствах native-потока нет (п. 3), поэтому сверять по PID ненадёжно, а по метке надёжно.
- Дорожка `them` пишется с monitor-источника. Проверено: `pw-record -P '{ stream.capture.sink=true }' --target <sink>` даёт source-output с `"source":52`, а 52 — это `alsa_output....sink.monitor` в `pactl list short sources`, и в свойствах есть `stream.capture.sink = "true"`. Такие потоки (чьи угодно, включая захват звука вкладки или экрана браузером) звонком не считаются: брать только потоки, чей `source` — не monitor. Monitor отличается полем `monitor_of_sink` или суффиксом `.monitor` в `pactl -f json list sources`.
- Чужие «измерители уровня». pavucontrol открывает на каждый источник поток `pa_stream_new(..., _("Peak detect"), ...)` с `PA_STREAM_PEAK_DETECT`, `application.id = "org.PulseAudio.pavucontrol"` (https://gitlab.freedesktop.org/pulseaudio/pavucontrol/-/blob/master/src/mainwindow.cc, `src/pavucontrol.cc`). Пока открыт pavucontrol, это ложный «звонок». Нужен denylist, как минимум `application.id=org.PulseAudio.pavucontrol`. Вкладка «Звук» в настройках Cinnamon, вероятно, делает то же самое. Не проверено.
- Во время проверки на машине уже висели два чужих `pw-record ... a_me.wav` / `a_them.wav` (параллельный прототип, не мой): они видны как source-output с `application.name = "pw-record"`. Если метки нет, наш поток неотличим от любого другого `pw-record`, поэтому метка `meetrec` обязательна.

## 5. Держит ли браузер поток весь звонок и открывает ли его заранее

- Спецификация (https://w3c.github.io/mediacapture-main/#life-cycle): когда все треки источника muted, disabled или stopped, UA «SHOULD relinquish the device within 3 seconds» и переоткрывает его при unmute. При `stop()` последнего трека «A source that is notified of a track ending will be stopped». Значит поток живёт, пока жив хотя бы один трек `getUserMedia`, а не пока длится звонок.
- Chrome устройство при `enabled=false` не отпускает: «Chromium does not honour the "SHOULD release the device when all tracks are disabled" part of the mediacapture spec» (https://github.com/nextcloud/spreed/pull/18788). Ещё 2019 год: «only Firefox turns off the device (and hardware light) in this case», Hangouts при mute отпускал только камеру, «the microphone track is left alone» (https://lists.w3.org/Archives/Public/public-webrtc-logs/2019Nov/0170.html, issue https://github.com/w3c/mediacapture-main/issues/642). Вывод: в Chrome mute в Meet поток не закрывает, звонок не рвётся.
- Firefox устройство при disable отпускает (там же). Если Meet или Zoom web в Firefox делают mute через `enabled=false`, поток может закрыться, и после 30 с mute звонок «кончится». Подтвердить, отпускает ли Firefox именно микрофон, первоисточник не дал. Проверить живым звонком.
- Заранее: экран предпросмотра Meet перед «Join now» показывает индикатор уровня микрофона, то есть `getUserMedia` уже вызван и поток открыт до входа во встречу (вторичный источник: https://www.laxis.com/blog/google-meet-test-call/). Запись начнётся с предпросмотра. Это безвредно: превью без звонка короче 2 мин удалится по правилу из map.
- Zoom desktop: первоисточника о моменте открытия и закрытия микрофона нет. Аудиотест в настройках, вероятно, тоже открывает поток. Проверить на живом звонке.

## Рекомендованный механизм

1. Подпроцесс `LC_ALL=C pactl subscribe`, строки фильтровать регуляркой `^Event '(new|remove)' on source-output #(\d+)$`. Остальное (`change`, `client`, `source`) игнорировать.
2. На каждое такое событие (и один раз при старте демона) делать снимок `LC_ALL=C pactl -f json list source-outputs` + `LC_ALL=C pactl -f json list sources` (только для множества monitor-индексов) и считать «чужие микрофонные потоки»:
   - `source` не monitor (`monitor_of_sink` пуст и имя не оканчивается на `.monitor`);
   - `properties."application.name" != "meetrec"`;
   - `properties."application.id"` не из denylist (`org.PulseAudio.pavucontrol`, при необходимости дополнить).
   Снимок вместо ведения состояния по индексам снимает гонки и пропущенные события.
3. Множество из пустого стало непустым → старт записи, в `notify-send` и журнал пишется `application.process.binary`/`application.name`. Множество пусто дольше 30 с → стоп.
4. Свои `pw-record` (обе дорожки) запускать с `-P '{ application.name=meetrec }'`. Дорожка `them` к тому же сидит на monitor и отсекается и правилом про monitor.

Allowlist (`chrome`, `chromium`, `firefox`, `zoom`) надёжнее против ложных срабатываний, но пропустит Telegram, Slack и прочие. Предлагаю denylist плюс журналирование бинаря, а allowlist оставить опцией конфига.

## Оговорки

- Начало и конец «звонка» = жизнь трека `getUserMedia`, а не встречи: включается предпросмотр (Meet green room); в Firefox, возможно, mute рвёт поток; тест микрофона в Zoom даёт короткие «звонки», их отсечёт правило 2 мин.
- Демон, запущенный посреди звонка, увидит поток только из начального снимка, поэтому снимок при старте обязателен.
- Если pipewire-pulse перезапустится, `pactl subscribe` завершится: демон перезапускает подписку.
- Поведение Chrome, Firefox и Zoom на этой машине живым звонком не проверено: всё выше получено из исходников и багтрекеров плюс опыта с `pw-record`/`parecord`. Перед кодом стоит один раз снять `pactl -f json list source-outputs` во время Meet в Chrome, Meet в Firefox (с mute дольше 30 с) и Zoom.
