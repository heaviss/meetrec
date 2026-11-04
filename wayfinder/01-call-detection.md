---
type: research
status: closed
assignee: claude
blocked_by: []
---

# Как заметить, что чужое приложение открыло микрофон

## Question

Каким механизмом PipeWire 1.0.5 (`pactl subscribe`, `pw-dump`/`pw-mon`, события `source-output`) демон узнаёт об открытии и закрытии потока записи с микрофона, как отличить приложение (Chrome/Firefox для Meet и Zoom web, приложение Zoom) и как исключить собственный `pw-record`? Держит ли браузер поток открытым весь звонок или открывает его заранее (превью камеры/микрофона)?

## Resolution

- Сигнал: `LC_ALL=C pactl subscribe`, строки `Event 'new'|'remove' on source-output #N`; на каждое событие и при старте снимок `pactl -f json list source-outputs` (проверено на PipeWire 1.0.5).
- Звонок = есть source-output на не-monitor источнике, у которого `application.name != meetrec` и который не в denylist (`org.PulseAudio.pavucontrol`). Приложение определяется по `application.process.binary`, `media.role` браузеры не ставят.
- Свои `pw-record` запускаются с `-P '{ application.name=meetrec }'`, у native-потока нет PID в свойствах. `them` и так отсекается как monitor.
- Chrome держит микрофон открытым и при mute. Firefox, возможно, отпускает его при mute, тогда звонок рвётся после 30 с. Meet открывает микрофон уже на экране предпросмотра. Для Zoom первоисточника нет, нужна проверка живым звонком.
- Подробно: [research/call-detection.md](research/call-detection.md)
