# Две дорожки `me` / `them` через `pw-record`

Тикет: [03-two-track-capture](../03-two-track-capture.md). Машина: PipeWire 1.0.5, WirePlumber 0.4.17 (Lua-конфиг), одна карта: sink `alsa_output…hw_Generic_1__sink`, default source — цифровой микрофон `hw:acp`.

## Коротко

- Две независимые `pw-record`: микрофон — default source, `them` — monitor default sink через `-P stream.capture.sink=true`. Обе следуют за сменой default-устройства (WirePlumber `follow = true`), пока не заданы `--target`/`target.object` и `node.dont-reconnect`.
- Monitor отдаёт сэмплы и в тишине (нули), поэтому дорожки идут вровень с часами. Замер: стартовый сдвиг ~21 мс, дрейфа за 90 с нет.
- Риск — разрывы: пока поток ни к чему не подключён (переключение устройства, профиль Bluetooth), сэмплы не приходят, а в файл не пишутся нули. Дорожка укорачивается, и всё, что после разрыва, съезжает раньше.
- SIGINT/SIGTERM дают корректный WAV. SIGKILL оставляет данные целыми, но в заголовке нулевые размеры; чинится перезаписью двух полей.

## Команды (проверены)

```bash
pw-record --rate 16000 --channels 1 --format s16 -P node.name=meetrec-me   me.wav
pw-record --rate 16000 --channels 1 --format s16 -P node.name=meetrec-them -P stream.capture.sink=true them.wav
```

`pw-link -l` во время записи:

```
alsa_output.pci-0000_03_00.6.HiFi__hw_Generic_1__sink:monitor_FR
  |-> meetrec-them:input_FR
alsa_input.pci-0000_03_00.6.HiFi__hw_acp__source:capture_FL
  |-> meetrec-me:input_FL
```

Стерео monitor сводится в моно внутри PipeWire: у потока порты `input_FL/FR`, `--channels 1` даёт моно-файл. Заголовок через python `wave`: `1 ch, 2 bytes, 16000 Hz`.

- `--rate`, `--channels`, `--format` обязательны для записи. Значения по умолчанию — 48000 / 2 / s16 (`pw-record --help`; https://docs.pipewire.org/page_man_pw-cat_1.html).
- `stream.capture.sink`: WirePlumber берёт для input-потока с этим свойством направление «sink» и цель — default `Audio/Sink`, а подключает его к monitor-портам (`getTargetDirection`/`getDefaultNode` в `/usr/share/wireplumber/scripts/policy-node.lua:279-296`; upstream https://gitlab.freedesktop.org/pipewire/wireplumber/-/blob/0.4.17/src/scripts/policy-node.lua). Ключ `PW_KEY_STREAM_CAPTURE_SINK`: https://docs.pipewire.org/group__pw__keys.html.
- Не передавать `--target`. Без него pw-cat не задаёт `target.object` (`pw-cat.c:1906-1907` — ставится только если `data.target` не NULL), и поток идёт по default. `--target 0` вообще отключает автоподключение (`pw-cat.c:1735-1738`).
- `media.role` оставить по умолчанию (`Music`). Роль `Communication` у потока сама переключает BT-гарнитуру в HSP/HFP (`policy-bluetooth.lua:315-323`, `media-role.use-headset-profile = true` в `policy.lua.d/10-default-policy.lua`).

## Смена устройства вывода посреди звонка

- В `/usr/share/wireplumber/policy.lua.d/10-default-policy.lua`: `["move"] = true` и `["follow"] = true, -- moves session items to the default device when it has changed`. Пользовательских переопределений нет: `~/.config/wireplumber` отсутствует.
- `policy-node.lua:653-656`: `local reconnect = not parseBool(si_props["node.dont-reconnect"])` … `if config.follow and default_nodes ~= nil and reconnect …`. На смену default (`policy-node.lua:898-903`) поток без явной цели перелинковывается: `link:remove ()` → `"... moving to new target"` (строки 731-746). С `node.dont-reconnect=true` он пишет `"... dont-reconnect, not moving"` и остаётся на старом устройстве, а если устройство пропало — ни к чему не подключён. Значит, `node.dont-reconnect` **не ставить**.
- Микрофон `me` идёт за default source так же. Если при подключении BT-гарнитуры default source станет её микрофоном, `me` переедет туда.
- Bluetooth: при удалении BT-устройства WirePlumber 2 с не линкует потоки на не-BT устройства (`policy-node.lua:1025-1026`: `"Bluetooth device removed, preventing non-Bluetooth devices from linking for 2 seconds"`). Это окно без сэмплов. Когда Meet/Zoom открывают BT-микрофон (`"Chromium input"`, `"ZOOM VoiceEngine"` в `media-role.applications`), гарнитура переходит A2DP → HSP/HFP, sink-узел пересоздаётся, `them` перелинковывается — ещё одна короткая дыра.
- `restore-target = true` (`main.lua.d/40-stream-defaults.lua`): если пользователь вручную перекинет поток `pw-record` в pavucontrol, WirePlumber запомнит цель и навяжет её следующим записям. Защита — `-P state.restore-target=false` (ключ читается в `restore-stream.lua:143`). Сценарий проверен по коду, на машине не запускался.
- Эмпирически не проверено: на машине один sink, а менять default запрещено условиями тикета.

## Синхронность дорожек

Замер: две `pw-record` стартуют одновременно, останавливаются `kill -INT` через 90 с (стенные часы 90,004 с):

```
a_me.wav   1439715 frames  89.982 s
a_them.wav 1439374 frames  89.961 s
```

Прогон на 6 с дал ту же разницу: 95203 − 94862 = 341 кадр = 21 мс. Значит, это постоянный стартовый сдвиг (sink был `SUSPENDED` и просыпался), а не дрейф. За 90 с дрейф ниже одного кадра. Устройства на разных ALSA-картах (`hw:Generic_1` и `hw:acp`), поэтому за час дрейф возможен, но речь идёт о десятках миллисекунд: часы аудиоустройств обычно расходятся на десятки ppm (оценка, не замер). Для транскрипта это не важно.

- Тишина: monitor без звука пишет нули на всю длину. 6 с записи без воспроизведения: `them.wav … 94862 frames, 5.93 s, peak 0`. Значит, пока поток подключён, обе дорожки идут вровень со стенными часами.
- Разрывы: pw-cat пишет в файл только из `on_process`. Неподключённый поток уходит в `PAUSED`, а `process` не вызывается (`pw-cat.c:741-747`, upstream https://gitlab.freedesktop.org/pipewire/pipewire/-/blob/1.0.5/src/tools/pw-cat.c). Дыра не заполняется нулями: дорожка становится короче, а всё после разрыва съезжает раньше на его длину.
- Рекомендация: запоминать стенное время старта каждой дорожки. При стопе считать `ожидаемые = (t_stop − t_start) × 16000` и сравнивать с `nframes`. Если расхождение больше ~0,5 с, логировать его и пометить в `transcript.md`, что после смены устройства тайминг `them` неточен. Стартовый сдвиг ~20 мс компенсировать не нужно.
- Если пропуски окажутся заметны на практике, есть альтернатива: писать `pw-record … -` в stdout и дописывать нули по часам в своём процессе. Но это уже свой рекордер, для MVP не нужен.

## Падение процесса и WAV

- pw-cat ловит `SIGINT` и `SIGTERM` (`pw-cat.c:1837-1838`, `do_quit` → `pw_main_loop_quit`), после цикла вызывает `sf_close(data.file)` (`pw-cat.c:2058-2059`), и libsndfile дописывает размеры в заголовок.
- Код выхода при остановке сигналом — **1**: `/* we're returning OK only if got to the point to drain */ if (data.drained) exit_code = EXIT_SUCCESS;` (`pw-cat.c:2037-2040`). При записи drain не наступает. Демону нельзя считать `exit 1` после своего SIGTERM ошибкой. Замер: `TERM exit=1`, `KILL exit=137`.
- SIGTERM через 4 с: заголовок корректный, `RIFF@\xed\x01\x00 … data\x1c\xed\x01\x00`, `wave nframes 63118`.
- SIGKILL через 4 с: `RIFF\x08\x00\x00\x00 … data\x00\x00\x00\x00`, файл 126278 байт. `wave.open` → `Error('fmt chunk and/or data chunk missing')`. Данные на месте. Ремонт — записать `filesize−8` по смещению 4 и `filesize−44` по смещению 40 (заголовок pw-record — ровно 44 байта). После этого `repaired nframes 63117 3.94 s`. libsndfile сама заголовок периодически не обновляет; это делает только `SFC_UPDATE_HEADER_NOW`/`SFC_SET_UPDATE_HEADER_AUTO`, а pw-cat их не вызывает (http://libsndfile.github.io/libsndfile/command.html#sfc_update_header_now).
- systemd при `stop` по умолчанию (`KillMode=control-group`) шлёт SIGTERM всем процессам юнита, включая дочерние `pw-record`. SIGKILL приходит через `TimeoutStopSec` (по умолчанию 90 с) (https://www.freedesktop.org/software/systemd/man/latest/systemd.kill.html). При штатном выключении файлы закрываются корректно. Ремонт нужен после OOM-kill, `kill -9` и потери питания; после потери питания может пропасть и хвост, ещё не сброшенный из page cache.

## Рекомендация

```bash
pw-record --rate 16000 --channels 1 --format s16 \
  -P node.name=meetrec-me -P state.restore-target=false \
  ~/Recordings/<stamp>/me.wav
pw-record --rate 16000 --channels 1 --format s16 \
  -P node.name=meetrec-them -P stream.capture.sink=true -P state.restore-target=false \
  ~/Recordings/<stamp>/them.wav
```

- Без `--target`, без `node.dont-reconnect`, без `media.role=Communication`.
- Стоп: `SIGTERM` (или `SIGINT`) обоим процессам и ждать завершения. Ожидаемый код выхода — 1.
- Перед расшифровкой проверять заголовок. Если `wave.open` падает, а файл больше 44 байт, чинить размеры RIFF/data по длине файла. Это же лечит встречи, оставшиеся после падения демона.
- Записывать стенное время старта и стопа каждой дорожки, сравнивать с `nframes` и логировать разрывы больше 0,5 с.

Оговорки:
- Следование за default sink и поведение при BT проверены по коду WirePlumber 0.4.17, не на живой смене устройства. После обновления до WirePlumber 0.5 (SPA-JSON-конфиг, `wireplumber.settings`) пере-проверить `linking.follow-default-target` и аналоги.
- Без наушников микрофон слышит динамики: речь собеседника попадёт и в `me`.
- `them` — весь системный вывод: уведомления и музыка тоже попадут в запись.
- `state.restore-target=false` выведен из кода `restore-stream.lua`, вживую не проверялся.
