---
type: research
status: closed
assignee: claude
blocked_by: []
---

# Как писать две дорожки синхронно

## Question

Как `pw-record` пишет микрофон и monitor default sink одновременно так, чтобы дорожки совпадали по времени? Что происходит при смене устройства вывода посреди звонка (наушники ↔ динамики, Bluetooth)? Какой формат (16 кГц mono s16) и как не потерять WAV при падении процесса?

## Resolution

- Две независимые `pw-record --rate 16000 --channels 1 --format s16`: `me` — default source, `them` — `-P stream.capture.sink=true`; без `--target` и `node.dont-reconnect`, тогда WirePlumber 0.4.17 (`follow = true`) переводит обе за сменой default-устройства.
- Monitor в тишине пишет нули; замер: стартовый сдвиг 21 мс, дрейфа за 90 с нет. Риск — разрывы при перелинковке (BT, смена устройства): сэмплы не пишутся, дорожка короче; детектировать по `nframes` vs стенное время.
- SIGTERM/SIGINT → корректный WAV (код выхода 1 — норма); SIGKILL → данные целы, размеры в заголовке 0, чинятся перезаписью смещений 4 и 40.
- Подробно: [research/two-track-capture.md](research/two-track-capture.md)
