---
type: task
status: open
assignee:
blocked_by: []
---

# Проверить, отпускает ли Firefox микрофон при mute

## Question

Живыми звонками снять `LC_ALL=C pactl subscribe` и `pactl -f json list source-outputs` ([рецепт](research/call-detection.md)): Meet в Firefox с mute дольше минуты, Meet в Chrome, приложение Zoom (когда открывает микрофон, отпускает ли при mute), экран предпросмотра Meet. Решение, которое ждёт проверка: пауза 30 с или 5 мин.
