---
label: wayfinder:map
---

# Локальная запись и расшифровка встреч на Linux

## Destination

План, по которому за одну сессию пишется демон `meetrec`: он сам замечает звонок, пишет дорожки `me` и `them`, расшифровывает их локально и кладёт `transcript.md` и `summary.md` в папку встречи. Все решения приняты, осталось писать код.

## Notes

- Машина: Ryzen 5 5600H (AVX2), без NVIDIA, 14 ГиБ RAM (свободно ~4,6), PipeWire 1.0.5, Cinnamon/X11, fish; есть `notify-send`, `uv`, `systemd --user`, `claude`.
- Контекст и альтернативы: `~/src/work-repo/docs/amanu-research.md`.
- Принятые при постановке рамки:
  - Python-скрипт через `uv`, демон под `systemd --user`, `pw-record` — подпроцесс; как вызывать `transcribe.cpp`, решает [Вызывать transcribe.cpp как CLI или через Python-биндинг](09-cli-or-binding.md).
  - Звонок = чужое приложение открыло поток записи с микрофона; конец — поток закрыт дольше 30 с.
  - Пишем сразу, `notify-send` на старте и стопе, встречи короче 2 мин удаляем.
  - `them` = monitor системного вывода целиком (браузер: Meet, Zoom web; приложение Zoom).
  - Только русский: GigaAM-v3.
  - Папка встречи `~/Recordings/<YYYY-MM-DD-HHMM>/`: `me.wav`, `them.wav`, `transcript.md`, `summary.md`; звук не удаляется.
  - Звук не покидает машину; текст транскрипта уходит в `claude -p`.
- Для grilling-тикетов: навыки `grilling` и `domain-modeling`.

## Decisions so far

- [Как заметить, что чужое приложение открыло микрофон](01-call-detection.md): `LC_ALL=C pactl subscribe` на `source-output` + снимок `pactl -f json list source-outputs`; звонок — не-monitor поток не от `meetrec`; свои `pw-record` метятся `application.name=meetrec`. Живым звонком не проверено.
- [Как писать две дорожки синхронно](03-two-track-capture.md): два `pw-record --rate 16000 --channels 1 --format s16` без `--target` (следуют за default-устройством), `them` с `stream.capture.sink=true`; сдвиг ~21 мс, дрейфа нет; при перелинковке BT теряются сэмплы; после SIGKILL чинить заголовок WAV.
- [Как transcribe.cpp расшифровывает русский на CPU](02-transcribe-cpp.md): `handy-computer/transcribe.cpp` v0.4.1, сборка `cmake` или колесо `transcribe-cpp`; модель `gigaam-v3-e2e-ctc-Q8_0.gguf` (272 МБ, с пунктуацией); длинное аудио режет сам; метки только по токенам (40 мс), сегменты собираем сами; оценка ~3–4 мин CPU на час дорожки (не замер); LocalVQE — отдельно, референс `them.wav`.
- [Почему система не замечает подключение наушников](10-headphones-detection.md): гипотеза — runtime PM кодека ALC256 теряет событие джека (`power_save=1`, `jackpoll_ms=0`); фикс для пользователя — `jackpoll_ms=,1000` в `snd_hda_intel`; на запись не влияет (`them` — monitor того же sink), демону хватит предупреждения при нулевом пике `me` дольше 60 с.

## Not yet specified

- Очередь расшифровки: встречи подряд, расшифровка во время следующего звонка, нагрузка на CPU.
- Падение демона или выключение посреди встречи: что остаётся на диске и как дорасшифровать.
- Установка: systemd-юнит, где лежат модели и бинарь `transcribe.cpp`, как обновлять.
- Как вручную перезапустить расшифровку или саммари для старой встречи (CLI).

## Out of scope

- Разметка спикеров внутри `them`: на CPU дорого, саммари обходится без неё.
- Другие языки и Parakeet: пока только русский.
- Локальная LLM для саммари: не хватает памяти.
- Захват звука отдельного приложения вместо всего системного вывода.
