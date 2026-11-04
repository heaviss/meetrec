---
type: research
status: open
assignee: claude
blocked_by: []
---

# Как заметить, что чужое приложение открыло микрофон

## Question

Каким механизмом PipeWire 1.0.5 (`pactl subscribe`, `pw-dump`/`pw-mon`, события `source-output`) демон узнаёт об открытии и закрытии потока записи с микрофона, как отличить приложение (Chrome/Firefox для Meet и Zoom web, приложение Zoom) и как исключить собственный `pw-record`? Держит ли браузер поток открытым весь звонок или открывает его заранее (превью камеры/микрофона)?
