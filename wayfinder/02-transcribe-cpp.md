---
type: research
status: closed
assignee: claude
blocked_by: []
---

# Как transcribe.cpp расшифровывает русский на CPU

## Question

Как собрать `transcribe.cpp` на Linux x86_64 (AVX2, без CUDA), где взять GigaAM-v3, как он режет длинное аудио (VAD, чанки), в каком виде отдаёт метки времени сегментов, сколько памяти ест и какая ожидаемая скорость на CPU? Есть ли в нём подавление эха (LocalVQE) и как его вызвать?

## Resolution

- Сборка: `cmake -B build && cmake --build build` (CPU, AVX2 через `GGML_NATIVE`), Vulkan опционально `-DTRANSCRIBE_VULKAN=ON`; либо без сборки `uv add transcribe-cpp` (колесо manylinux x86_64: CPU all-variants + Vulkan).
- Модель: `gigaam-v3-e2e-ctc-Q8_0.gguf`, 272 МБ, WER 5,53 % FLEURS-ru, с пунктуацией; длинное аудио режется внутри окнами по 25 с, лимита нет, VAD не нужен.
- Меток сегментов у GigaAM нет — только токены по 40 мс (`--timestamps token`, текстовый stdout; в `--batch-jsonl` их нет); сегменты собираем сами (как amanu: куски по 20 с, или слова из токенов).
- Скорость (опубликовано, Ryzen 7 4750U + Vega): CPU 16–20× RT, Vulkan 33–35× RT; RSS не опубликован, оценка ≤ ~1 ГБ на час.
- LocalVQE — отдельная библиотека, не часть transcribe.cpp; нужен референс (`them.wav`): `localvqe localvqe-v1.4-aec-200K-f32.gguf --in-wav me.wav them.wav --out-wav me.clean.wav`.
- Подробно: [research/transcribe-cpp.md](research/transcribe-cpp.md)
