---
type: grilling
status: closed
assignee: claude
blocked_by: [11]
---

# Как ставить и обновлять meetrec

## Question

Как ставится всё вместе: Python-пакет через `uv` (`uv tool install`?), юнит `systemd --user`, модель GigaAM в `~/.cache/meetrec/models/`, колесо `transcribe-cpp==0.4.1`, собранный LocalVQE и его модель, конфиг (путь к глоссариям, имя пользователя, пауза). Как обновлять закреплённые версии и где лежат логи.

## Resolution

- meetrec — Python-пакет в этом репо, `uv tool install --editable ~/PycharmProjects/meetrec` на Python 3.14; `transcribe-cpp==0.4.1` закреплён в `pyproject.toml`; на PyPI не публикуется. Правка кода — перезапуск сервиса.
- `meetrec setup`, идемпотентный: качает GigaAM и модель LocalVQE с проверкой sha256, собирает `liblocalvqe.so` из закреплённого коммита (`uvx cmake`, `-DLOCALVQE_BUILD_SHARED=ON`, цель `localvqe_shared`), ставит и включает юнит `systemd --user`; готовое пропускает.
- Файлы: модели и `liblocalvqe.so` — `~/.local/share/meetrec/` (`setup` переносит из `~/.cache/meetrec/`); конфиг — `~/.config/meetrec/config.toml` через `tomllib`, необязательный (папка записей, путь к work-repo, имя пользователя, пауза); встречи — `~/Recordings/`.
- Юнит: `Restart=on-failure`, `After=pipewire.service`, `WantedBy=default.target`, `KillMode=control-group` (SIGTERM даёт `pw-record` закрыть WAV). Логи — stdout в journald (`journalctl --user -u meetrec`), ошибки встречи — в `meta.json`.
- Обновление вручную: поднять версию или коммит, `meetrec setup`, перезапуск; после смены `transcribe-cpp` — `meetrec redo --all` на эталонной встрече из `~/Recordings/bench` и сверка качества. Автообновлений нет.
