---
type: task
status: open
assignee: claude
blocked_by: []
---

# Проверить, что LocalVQE не портит запись в наушниках

## Question

Собрать LocalVQE (`cmake` через `uvx`, заголовки `libsndfile` — `apt`, нужен sudo), записать две дорожки `me` / `them` разговора в наушниках (по [рецепту записи](research/two-track-capture.md)) и прогнать `me` через LocalVQE. Портит ли он чистый голос: сравнить расшифровку GigaAM `me.wav` и `me.clean.wav`, послушать. Решение, которое ждёт проверка: LocalVQE на каждой встрече или только при порте Speaker.

## Steps

Без `libsndfile`: нужна только разделяемая библиотека с C API (`LOCALVQE_BUILD_SHARED`), WAV читает Python. Исходники — `~/.cache/meetrec/src/LocalVQE` (`7f61cd0`), модель — `~/.cache/meetrec/models/localvqe-v1.4-aec-200K-f32.gguf` (2 924 224 Б).

1. Сборка (руками: авто-режим агента не компилирует сторонний код):
   `cd ~/.cache/meetrec/src/LocalVQE && uvx cmake -S ggml -B ggml/build -DCMAKE_BUILD_TYPE=Release -DLOCALVQE_BUILD_SHARED=ON && uvx cmake --build ggml/build -j6 --target localvqe_shared`
2. В наушниках включить видео с речью (это `them`) и 2 минуты говорить поверх него и в паузах: `checks/record-two-tracks.sh 120`.
3. `uv run --with transcribe-cpp==0.4.1 python -I checks/localvqe_check.py <папка из шага 2>` — пишет `me.clean.wav`, уровни и три расшифровки; послушать `me.wav` против `me.clean.wav`.
