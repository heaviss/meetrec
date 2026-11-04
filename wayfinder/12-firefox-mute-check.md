---
type: task
status: closed
assignee: claude
blocked_by: []
---

# Проверить, отпускает ли Firefox микрофон при mute

## Question

Живыми звонками снять `LC_ALL=C pactl subscribe` и `pactl -f json list source-outputs` ([рецепт](research/call-detection.md)): Meet в Firefox с mute дольше минуты, Meet в Chrome, приложение Zoom (когда открывает микрофон, отпускает ли при mute), экран предпросмотра Meet. Решение, которое ждёт проверка: пауза 30 с или 5 мин.

## Steps

`checks/watch-mic.sh` пишет в `~/Recordings/check-mic-<время>.log` каждое событие `source-output` и кто держит микрофон. Запустить, затем по очереди, отмечая время:

1. Meet в Firefox: экран предпросмотра 20 с → войти → mute на 60 с → unmute → выйти.
2. То же в Chrome.
3. Приложение Zoom: открыть → войти в встречу → mute на 60 с → выйти.

Ctrl-C, лог — агенту.

## Answer

Звонок в Firefox 2026-11-04, лог в `~/Recordings/check-mic-2026-11-04-192951.log`. Firefox занял микрофон на экране предпросмотра и держал его 30 с там, затем 30 с при mute. Поток ни разу не пропал и не стал corked. При входе во встречу Firefox пересоздал поток: новый появился раньше, чем ушёл старый, так что пауза не началась. Микрофон ушёл только с выходом из звонка.

Решение: `pause_s = 30`. Chrome держит микрофон при mute по документации. Приложение Zoom не проверено.
