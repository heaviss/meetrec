---
type: grilling
status: open
assignee:
blocked_by: []
---

# Как ставить LocalVQE по желанию

## Question

`echo_cancel` по умолчанию выключен, а `meetrec setup` всё равно клонирует и собирает LocalVQE: для этого нужны `git`, `g++` и `cmake`. Как сделать установку по желанию: собирать только при `echo_cancel = true`, отдельная команда или флаг `setup`? Что делает демон, если `echo_cancel = true`, а библиотеки нет? Попутно убрать то, что годится только для этой машины: `-j6` в `install.py` и перенос из старого `~/.cache/meetrec`.
