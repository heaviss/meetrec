---
type: task
status: open
assignee: claude
blocked_by: []
---

# Составить список замен для истории

## Question

Что именно вычистить из всех коммитов `master` (содержимое файлов и сообщения коммитов), чтобы история стала публичной? Нужен готовый файл замен для `git filter-repo --replace-text` и mailmap для почты. Известно:

- цитаты рабочей встречи в `wayfinder/research/benchmark.md`: имена коллег, клиенты, внутренние темы, имя файла `meeting-86min`;
- имя пользователя по умолчанию в `config.py`, README и SPEC;
- `work-repo` и путь к `amanu-research.md` в `wayfinder/` и коде;
- `9004182+heaviss@users.noreply.github.com` в авторах и CLAUDE.md.

Пройти весь `git log master -p` и найти остальное. Чистить ли описание машины в `wayfinder/map.md` (процессор, память) — решить здесь же. Узнать числовой id аккаунта `heaviss` на GitHub для noreply-адреса.
