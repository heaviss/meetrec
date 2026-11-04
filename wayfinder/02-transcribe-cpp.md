---
type: research
status: open
assignee: claude
blocked_by: []
---

# Как transcribe.cpp расшифровывает русский на CPU

## Question

Как собрать `transcribe.cpp` на Linux x86_64 (AVX2, без CUDA), где взять GigaAM-v3, как он режет длинное аудио (VAD, чанки), в каком виде отдаёт метки времени сегментов, сколько памяти ест и какая ожидаемая скорость на CPU? Есть ли в нём подавление эха (LocalVQE) и как его вызвать?
