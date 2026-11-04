---
type: research
status: closed
assignee: claude
blocked_by: []
---

# Какой моделью распознавать английскую речь

## Question

Какие английские или многоязычные модели умеет `transcribe-cpp` 0.4.1 (и upstream `handy-computer/transcribe.cpp`) в формате GGUF: Parakeet, Whisper, Canary, другие. Для каждой: размер, лицензия, есть ли пунктуация, отдаёт ли метки токенов или слов (на них собирается `transcript.md`, см. `wayfinder/06-transcript-format.md`), умеет ли определять язык. Какая годится на CPU/Vulkan без NVIDIA с той же скоростью, что GigaAM-v3 (`wayfinder/research/benchmark.md`).

## Resolution

`parakeet-tdt-0.6b-v2` Q8_0: 730 МБ, CC-BY-4.0, пунктуация и регистр встроены, метки токенов через тот же `run(timestamps="token")`. Находки и замер: [research/english-models.md](research/english-models.md).

- На этой машине медленнее GigaAM примерно на 10 % (CPU 4 потока 10,6× против 11,8×, Vulkan 19,3× против 21,6×); расшифровка сразу после встречи остаётся.
- Whisper отдаёт только сегменты, Canary, Qwen3, Granite, Cohere, Voxtral меток не дают — отпадают.
- Многоязычные `parakeet-ultra`/v3 (25 языков с автоопределением) для русского хуже GigaAM. Отдельно определить язык может `lang-id-voxlingua107-ecapa` (27 МБ, Apache-2.0).
- Правки: в `Token.text` у Parakeet ведущий пробел вместо `▁` — заменить в `transcribe_track`, иначе `transcript.words()` склеит всё в одно слово; модель по языку, `language` вместо зашитого `"ru"`; модель в `install.MODELS` и путь в `Config`.
- Не измерено: пик памяти Parakeet на часовой записи.
