# meetrec — спецификация первой версии

Демон для Linux. Сам замечает звонок, пишет две дорожки: `me` (микрофон) и `them` (системный вывод). Локально расшифровывает их (русский — GigaAM-v3, английский — Parakeet TDT 0.6B v2) и кладёт в папку встречи `transcript.md` и `summary.md`. Термины — в [GLOSSARY.md](../GLOSSARY.md). Почему решено именно так, рассказывают тикеты [карты](map.md); здесь только *что* строить. Ссылка вида «→ 08» ведёт на тикет `08-*.md` рядом.

Машина: Ryzen 5 5600H, iGPU Vega (RADV), без NVIDIA. PipeWire 1.0.5 + WirePlumber 0.4.17, Cinnamon/X11. Python 3.14 через `uv`.

## 1. Рамки

Входит:
- автостарт и автостоп по микрофону;
- две дорожки;
- расшифровка на русском или английском, один язык на встречу;
- подавление эха только при динамиках и только с `echo_cancel = true`;
- транскрипт и саммари через `claude -p`;
- `status` / `redo` / `setup`.

Не входит:
- разметка спикеров внутри `them`;
- другие языки и смешанные встречи;
- локальная LLM;
- захват звука отдельного приложения;
- ручной старт и стоп записи;
- автообновление.

## 2. Пакет и раскладка

```
pyproject.toml          # requires-python >=3.14; deps: transcribe-cpp==0.4.1 + transcribe-cpp-native==0.4.1; dev: pytest, mypy, wemake-python-styleguide
setup.cfg               # flake8/wemake config
meetrec/
  cli.py                # meetrec run | status | redo | setup
  config.py             # defaults + ~/.config/meetrec/config.toml (tomllib)
  meeting.py            # Meeting folder, meta.json, statuses and their transitions, crash recovery
  detect.py             # pactl snapshots → "is a call on" + active port
  pactl_events.py       # pactl subscribe → mic / sink events
  record.py             # Recorder protocol; two pw-record processes, silence probe
  session.py            # the meeting being recorded: apps, ports, dead tracks, silence
  processing.py         # FIFO of closed meetings, the worker process, rescan
  lifecycle.py          # Lifecycle state machine: idle ⇄ recording ⇄ pause → close | discard
  watcher.py            # pactl snapshots → Lifecycle → Session: starts, closes, discards meetings
  daemon.py             # event loop: pactl snapshots, signals, processing, state.json
  process.py            # worker: stage plan → LocalVQE → GigaAM → tokens.tsv → transcript.md → summary.md
  asr.py                # GigaAM via transcribe-cpp, one child process per track
  echo.py               # LocalVQE via ctypes
  audio.py              # 16 kHz mono s16 WAV I/O, WAV header repair
  transcript.py         # tokens → phrase lines → transcript.md
  summary.py            # prompt + claude -p
  install.py            # meetrec setup
  prompt.md             # summary prompt
tests/                  # one small test per non-trivial logic, see §11
```

Других зависимостей нет: WAV читается через `wave`, LocalVQE вызывается через `ctypes`, конфиг — через `tomllib`. Проверки: `pytest`, `mypy --strict`, `flake8` с wemake-python-styleguide (пороги в `setup.cfg`), `ruff`.

## 3. Конфиг

`~/.config/meetrec/config.toml` необязателен. Значения по умолчанию:

| ключ | по умолчанию | → |
|---|---|---|
| `recordings_dir` | `~/Recordings` | |
| `pause_s` | `30`: Firefox, как и Chrome, держит микрофон при mute и на экране предпросмотра | 08, 12 |
| `min_meeting_s` | `120` | 08 |
| `silent_mic_s` | `60` | 10 |
| `echo_cancel` | `false`: в наушниках гнездо не всегда распознаётся, и PipeWire показывает `[Out] Speaker` | 11 |
| `language` | `ru`: язык речи на встречах, `ru` или `en`. Выбирает модель, язык саммари и модель, которую качает `setup`. Смешанные встречи не поддерживаются, язык сам не определяется | [public-release 06](../.scratch/public-release/06-language-choice.md) |
| `user_name` | полное имя из поля GECOS (`pwd`, до первой запятой), если пусто — логин | 07 |
| `glossary_repo` | нет: без него саммари идёт без словаря | 07 |
| `app_denylist` | `["org.PulseAudio.pavucontrol"]` (по `application.id`) | 01 |
| `data_dir` | `~/.local/share/meetrec` | 14 |

## 4. Папка встречи

`<recordings_dir>/<YYYY-MM-DD-HHMM>/`. Если такая папка уже есть, добавляется суффикс `-2`.

| файл | кто пишет |
|---|---|
| `me.wav`, `them.wav` | `pw-record`, 16 кГц mono s16 |
| `meta.json` | демон и worker |
| `me.clean.wav` | worker, только если запускался LocalVQE |
| `me.tokens.tsv`, `them.tokens.tsv` | worker: `t0_ms\tt1_ms\tpiece` |
| `transcript.md`, `summary.md` | worker |

`meta.json`:

```json
{
  "status": "recording | pause | queued | processing | done | error",
  "started_at": "ISO-8601, local tz",
  "stopped_at": null,
  "apps": [{"binary": "firefox", "name": "Firefox", "first_seen": "…"}],
  "ports": [{"at": "…", "sink": "…", "port": "[Out] Headphones"}],
  "gaps": [{"track": "them", "at": "…", "lost_s": 1.8}],
  "warnings": ["mic silent 60 s at …"],
  "language": "ru | en",
  "summary_done": false,
  "summary_skipped": false,
  "error": null,
  "redo": "missing | transcript | all | null",
  "stage": "transcribe | summary | null"
}
```

`language` worker берёт из конфига при первой обработке, `redo --language` его меняет. `summary_skipped: true` — `claude` не нашёлся в `PATH`.

`status` — единственный источник правды о состоянии. Запись идёт атомарно: во временный файл, затем `os.replace`.

## 5. Как заметить звонок (`detect.py`) → 01

1. Подпроцесс `LC_ALL=C pactl subscribe`. Учитываются только строки `^Event '(new|remove)' on source-output #\d+$` и `^Event 'change' on (sink|server) #\S+$`; `sink-input` (громкость любого потока) — нет. `LC_ALL=C` обязателен: без него `pactl` выводит события по-русски, а `-f json` падает на не-ASCII.
2. На каждое такое событие, а также при старте демона снимаются `LC_ALL=C pactl -f json list source-outputs` и `… list sources`. Поток считается **чужим микрофонным**, если:
   - его источник не monitor (`monitor_of_sink` пуст и имя не кончается на `.monitor`);
   - `application.name != "meetrec"`;
   - `application.id` не входит в `app_denylist`.
3. «Звонок идёт» ⇔ есть хотя бы один чужой микрофонный поток. Бинарь и имя приложения пишутся в `meta.json.apps`.
4. Если `pactl subscribe` завершился (перезапуск pipewire-pulse), подписка перезапускается, а состояние берётся из нового снимка.
5. Активный порт: на события `change` по `sink` и `server` снимается `pactl -f json list sinks`, берётся `active_port` default sink. Если порт изменился, в `meta.json.ports` добавляется запись. На этой машине порты называются `[Out] Speaker` и `[Out] Headphones`.

## 6. Запись (`record.py`) → 03, 10

```bash
pw-record --rate 16000 --channels 1 --format s16 \
  -P '{ application.name=meetrec node.name=meetrec-me state.restore-target=false }' me.wav
pw-record --rate 16000 --channels 1 --format s16 \
  -P '{ application.name=meetrec node.name=meetrec-them stream.capture.sink=true state.restore-target=false }' them.wav
```

- Флаги `--target`, `node.dont-reconnect` и `media.role` не ставятся. Без них обе дорожки следуют за default-устройством, а роль Communication переключила бы BT-гарнитуру в HSP.
- Оба процесса стартуют подряд. Остановка: `SIGTERM` обоим и ожидание завершения. Код выхода 1 после `SIGTERM` — норма.
- Сохраняется стенное время старта и стопа. При закрытии `nframes / 16000` сравнивается с прошедшим временем. Расхождение больше 0,5 с пишется в `gaps` и в журнал: это потери при перелинковке Bluetooth.
- Тишина микрофона: раз в 10 с читаются последние 10 с `me.wav` (файл растёт). Если пик равен 0 дольше `silent_mic_s`, отправляется одно `notify-send` за встречу и добавляется запись в `warnings`.
- Каждую секунду демон проверяет, живы ли оба `pw-record`. Умерший процесс даёт одно `notify-send` и запись в `warnings`; встреча пишется дальше одной дорожкой.

## 7. Демон (`daemon.py`, `watcher.py`) → 08

```
Ожидание ──звонок──▶ Запись ──микрофон свободен──▶ Пауза ──pause_s истёк──▶ Закрыта
                       ▲                             │
                       └──────звонок снова───────────┘
Закрыта: длительность < min_meeting_s → удалить папку молча; иначе → queued
queued → processing (worker) → done | error
```

- Во время Паузы `pw-record` продолжает писать: при возврате в Запись дорожки идут дальше без разрыва, а при закрытии хвост паузы просто остаётся в файлах.
- **Длительность встречи** — от старта до момента, когда микрофон освободили в последний раз (`stopped_at`), без хвоста Паузы. Момент освобождения пишется в `stopped_at` сразу при переходе в Паузу и стирается при возврате в Запись, так что падение в Паузе его не теряет. У встречи, упавшей в Записи, `stopped_at` = `started_at` + длина `me.wav`.
- Одна встреча пишется в каждый момент времени. Если звонок начался во время Паузы, это продолжение той же встречи.
- Уведомления `notify-send`: старт записи, стоп с длительностью, саммари готово с путём к `summary.md`, ошибка, молчащий микрофон. Удаление короткой встречи проходит без уведомления.
- Очередь обработки: FIFO, по одной встрече. Пока идёт Запись или Пауза, worker не запускается. Если звонок начался во время обработки, группа процессов worker'а получает `SIGSTOP` и `SIGCONT` после закрытия встречи: iGPU и CPU остаются звонку. Исключение — этап `summary` (`meta.stage`): он ждёт только сеть, а таймаут `claude` шёл бы и во время остановки. У worker'а есть бюджет `1800 с + длительность встречи` по времени работы без остановок; превысил — `SIGKILL` группе и `error`. Worker, вышедший с ненулевым кодом в `queued` или `processing`, тоже ставит встрече `error`.
- Сбой `pactl` (не запустился, упал, битый JSON) не роняет демон: остаётся прежний снимок, ошибка — в журнал. Упавшая подписка перезапускается через секунду, снимки — после этой секунды.
- Если `echo_cancel = true`, а библиотеки или модели LocalVQE нет, демон при старте шлёт одно уведомление «эхо не подавляется: запустите meetrec setup» и пишет `me.wav` как есть.
- `SIGUSR1` только ставит флаг пересканирования: `queue.Queue` нереентерабелен, обработчик сигнала его не трогает.
- Старт демона и `SIGUSR1`: просмотр `recordings_dir`.
  - `recording` или `pause` (демон упал посреди встречи): починить заголовки WAV (§8) и поставить `queued`; встреча короче `min_meeting_s` удаляется, как при обычном закрытии.
  - `processing`: снова `queued`.
  - Все `queued` по возрастанию `started_at` встают в очередь.
- Остановка демона (`SIGTERM` от systemd): обработчик только ставит `threading.Event`, цикл выходит на следующем тике, `contextlib.closing` закрывает встречу. `pw-record` получает `SIGTERM` и закрывает WAV. Сессия отцепляется от `Watcher` до закрытия, поэтому остановка посреди закрытия не тронет уже закрытую встречу. Встреча переходит в `queued` и обработается при следующем старте; встреча короче `min_meeting_s` удаляется, как при обычном закрытии. Это же происходит при любом другом падении цикла демона. Если звонок ещё идёт, после старта начнётся новая встреча: перезапуск посреди звонка режет её на две папки — принято.

## 8. Починка WAV

Если `wave.open` падает, а файл длиннее 44 байт (так бывает после `SIGKILL`, OOM или потери питания), в заголовок записываются размеры: по смещению 4 — `filesize − 8`, по смещению 40 — `filesize − 44` (little-endian uint32). → 03

## 9. Обработка (`process.py`) → 05, 06, 07, 09, 11

Worker запускается отдельным процессом под `nice -n 19` в своей группе процессов: `python -m meetrec.process meeting <папка>`. Что делать, решает план из `meta.redo` (`missing`, если пусто) и готовых файлов; `redo` очищается только при `done`, так что упавший посреди `redo --all` worker повторит то же самое. Подкоманды `track <wav> <tsv> <backend> <language>` и `echo <mic> <ref> <out>` — дочерние процессы расшифровки и LocalVQE.

1. **LocalVQE**, только если `echo_cancel = true` и в `meta.json.ports` хоть раз был `[Out] Speaker`. На этой машине гнездо наушников часто не распознаётся: наушники `not available`, звук идёт в `[Out] Speaker` на малой громкости, так что по порту наушники от динамиков не отличить. Дорожки обрезаются до общей длины, затем вызывается `localvqe_new(model)` и `localvqe_process_s16(ctx, me, them, n, out)` из `<data_dir>/liblocalvqe.so` через `ctypes`; результат пишется в `me.clean.wav`. Перед `liblocalvqe.so` по пути загружаются `libggml-base.so.0` и `libggml.so.0`. LocalVQE запускается в дочернем процессе (`python -m meetrec.process echo me.wav them.wav me.clean.wav`): если он упал, даже нативно, берётся исходный `me.wav`, а в `warnings` добавляется запись. В наушниках LocalVQE снижает громкость на 13 дБ и добавляет гул (→ 11), поэтому всегда его не включаем.
2. **Расшифровка**: каждая дорожка (`me.clean.wav` или `me.wav`, затем `them.wav`) идёт в своём дочернем процессе. Дорожку без файла или без единого кадра (её `pw-record` умер сразу) worker не расшифровывает: пишет пустой `.tokens.tsv` и запись в `warnings`, вторая дорожка расшифровывается как обычно:
   ```python
   tc.Model(model_path, backend="vulkan").session().run(pcm_f32, language=meta.language, timestamps="token")
   ```
   Модель — по `meta.language`: `ru` → `gigaam-v3-e2e-ctc-Q8_0.gguf`, `en` → `parakeet-tdt-0.6b-v2-Q8_0.gguf`. Если файла нет, встреча получает `error` с подсказкой запустить `setup` для этого языка.
   Если процесс упал или вернул ошибку, один повтор с `backend="cpu"` и `session(n_threads=4)`. Если упал и он, встреча получает `error` и уведомление. Токены пишутся в `<track>.tokens.tsv`. Пиковое потребление памяти на час дорожки у GigaAM — около 1,6 ГиБ, поэтому дорожки идут по одной. Модель без `supports("long_form")` (Parakeet) получает дорожку кусками до 300 с. Каждый кусок кончается на самой тихой 0,1 с из последних 10 с, метки сдвигаются на начало куска. Без нарезки память Parakeet растёт с длиной, ~1,4 ГиБ на 5 мин на CPU, а час падает с `backend error`. С нарезкой час английской речи на этой машине: Vulkan — 2:24 и 0,57 ГиБ RSS, CPU — 6:12 и 2,6 ГиБ.
3. **Транскрипт** (`transcript.py`) → 06:
   - Слово начинается с токена на `▁` (GigaAM) или на пробел (Parakeet) и продолжается до следующего такого токена. Время слова — от `t0` первого токена до `t1` последнего.
   - Фраза — подряд идущие слова одной дорожки. Новая фраза начинается, если пауза между словами ≥ 1000 мс, или если фраза длиннее 15 с и предыдущее слово кончается на `.?!`.
   - Фразы обеих дорожек сортируются по времени начала, перекрытия не обрабатываются.
   - Формат:
     ```
     # Встреча 2026-11-02 17:30

     Длительность: 01:26:14

     **[00:00:16] them:** текст фразы

     **[00:00:34] me:** текст фразы
     ```
   - Текст идёт как распознан, без чистки.
4. **Саммари** (`summary.py`) → 07:
   - Вызов: `claude -p --no-session-persistence --tools "" --setting-sources project --system-prompt-file meetrec/prompt.md` из временной папки, вход через stdin:
     ```
     <glossary>
     ### <path>
     <content>   # every GLOSSARY-MAP.md and *GLOSSARY.md of glossary_repo, by git ls-files
     </glossary>

     <transcript>
     …
     </transcript>
     ```
   - Системный промпт — `meetrec/prompt.md`, по-английски. `{user_name}` подставляется из конфига, `{language}` — название языка встречи: саммари пишется на нём. Русская версия проверена на встрече 2 ноября, ветка `prototype/summary`.
   - Без `glossary_repo` блока `<glossary>` нет.
   - Если `claude` нет в `PATH`, саммари пропускается: `summary_skipped: true`, `status` такую встречу не показывает.
   - Если `claude` упал, встреча всё равно получает `done`, но с `summary_done: false`, и приходит уведомление.

## 10. CLI → 13, 14

- `meetrec run` — демон, его запускает юнит.
- `meetrec status` — показывает:
  - состояние демона (его пишет `<data_dir>/state.json`);
  - очередь;
  - встречи с `error` или с `summary_done: false` без `summary_skipped`.
- `meetrec redo <папка> [--transcript | --all] [--language ru|en]`:
  - Встречу в `recording`, `pause` или `processing` команда не трогает и печатает её статус.
  - Что доделывается:
    - без флага — всё, чего не хватает;
    - `--transcript` — `transcript.md` из `*.tokens.tsv`, затем саммари;
    - `--all` — всё заново, с расшифровкой;
    - `--language` — меняет `meta.language` и включает `--all`.
  - Сама команда ничего не считает: пишет `queued` и нужный этап в `meta.json`, затем `systemctl --user kill --kill-whom=main -s USR1 meetrec` (без `--kill-whom=main` сигнал уйдёт всей группе и убьёт `pw-record`).
- `meetrec setup` можно запускать повторно, готовые шаги пропускаются:
  1. Модели скачиваются в `<data_dir>/models/` с проверкой sha256: модель языка из `language` и, только при `echo_cancel = true`, модель LocalVQE. После смены языка или включения `echo_cancel` `setup` запускают заново.
     - `gigaam-v3-e2e-ctc-Q8_0.gguf` ← `https://huggingface.co/handy-computer/gigaam-v3-e2e-ctc-gguf/resolve/main/gigaam-v3-e2e-ctc-Q8_0.gguf`, sha256 `9ccce4750dc813a493d96ca15ee251712bedec15ac9a02fa3d2bd732f08ae5eb`
     - `parakeet-tdt-0.6b-v2-Q8_0.gguf` ← `https://huggingface.co/handy-computer/parakeet-tdt-0.6b-v2-gguf/resolve/main/parakeet-tdt-0.6b-v2-Q8_0.gguf`, sha256 `f0d0e99cebb6d3b83f1f7069b82b5d3c2e39a54545b0da039cb4bafd9c4e5caa`
     - `localvqe-v1.4-aec-200K-f32.gguf` ← `https://huggingface.co/LocalAI-io/LocalVQE/resolve/main/localvqe-v1.4-aec-200K-f32.gguf`, sha256 `b6e43138588a83bfe903ab5e143b4020b91c1e1629f5a575ac5855ff0003c731`
  2. LocalVQE, только при `echo_cancel = true`: `git clone --recursive https://github.com/localai-org/LocalVQE` на коммите `7f61cd0`, затем `uvx cmake -S ggml -B ggml/build -DCMAKE_BUILD_TYPE=Release -DLOCALVQE_BUILD_SHARED=ON` и `uvx cmake --build ggml/build --parallel --target localvqe_shared`. Исходники и сборка лежат в `<data_dir>/src/LocalVQE`; библиотека — `ggml/build/bin/liblocalvqe.so`. Её RUNPATH указывает на папку сборки, поэтому `libggml-base.so.0` и `libggml.so.0` загружаются явно по пути с `RTLD_GLOBAL`.
  3. Юнит `~/.config/systemd/user/meetrec.service`, затем `systemctl --user daemon-reload` и `enable --now`:
     ```ini
     [Unit]
     Description=meetrec: record, transcribe and summarize calls
     After=pipewire.service pipewire-pulse.service
     [Service]
     ExecStart=%h/.local/bin/meetrec run
     Environment=PYTHONUNBUFFERED=1
     Restart=on-failure
     KillMode=control-group
     [Install]
     WantedBy=default.target
     ```
- Установка: `uv tool install git+https://github.com/heaviss/meetrec --python 3.14`, затем `meetrec setup`. Для разработки — `uv tool install --editable . --python 3.14` из клона.
- Обновление: `uv tool upgrade meetrec`, затем `meetrec setup` и `systemctl --user restart meetrec`. После смены `transcribe-cpp` прогнать `meetrec redo --all` на эталонной встрече `~/Recordings/bench` и сверить качество.
- Логи демона идут в stdout и попадают в journald (`journalctl --user -u meetrec`).

## 11. Проверки

На каждую нетривиальную логику — один маленький тест в `tests/`, на pytest без фикстур:

- `detect`: из JSON-снимка `source-outputs`/`sources` выделяются чужие микрофонные потоки. Monitor, `meetrec` и pavucontrol отсекаются.
- `daemon`: таймлайн событий (старт, освобождение, возврат внутри паузы, истечение паузы, короткая встреча) переводится в нужные действия `Lifecycle`. Время инжектится, без `sleep`.
- `process`: план этапов для `missing` / `transcript` / `all` при разных наборах готовых файлов.
- `processing`: встреча, оставшаяся в `recording` после падения, уходит в `queued` с длительностью по `me.wav`; упавшая в Паузе сохраняет момент освобождения; worker, умерший до начала работы, даёт `error`; битый `meta.json` пропускается.
- `meeting`: заголовок WAV, обрезанный как после `SIGKILL`, чинится, и `wave.open` читает верное число кадров.
- `transcript`: границы фраз, формат строк и чередование `me`/`them` — на синтетических токенах. Фрагменты настоящих встреч в репозиторий не кладём: это чужая речь.

Ручная приёмка — первый живой звонок:
- запись стартовала и остановилась;
- в `meta.json` видны приложения и порт;
- `transcript.md` и `summary.md` пришли через несколько минут после конца встречи.

## 12. Открыто

- Приложение Zoom живым звонком не проверено: если оно отпускает микрофон при mute дольше 30 с, встреча разорвётся на две.
- Не проверено вживую:
  - поведение Chrome и Zoom;
  - следование за default sink при смене устройства;
  - уживается ли Vulkan-расшифровка с видеозвонком, если звонок начат вне демона (worker во время Записи остановлен).
