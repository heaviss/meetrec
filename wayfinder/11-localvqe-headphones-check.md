---
type: task
status: open
assignee:
blocked_by: []
---

# Проверить, что LocalVQE не портит запись в наушниках

## Question

Собрать LocalVQE (`cmake` через `uvx`, заголовки `libsndfile` — `apt`, нужен sudo), записать две дорожки `me` / `them` разговора в наушниках (по [рецепту записи](research/two-track-capture.md)) и прогнать `me` через LocalVQE. Портит ли он чистый голос: сравнить расшифровку GigaAM `me.wav` и `me.clean.wav`, послушать. Решение, которое ждёт проверка: LocalVQE на каждой встрече или только при порте Speaker.
