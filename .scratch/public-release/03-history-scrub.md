---
type: task
status: closed
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

## Resolution

Файлы замен лежат вне дерева, в `.git/public-release/`: в них сами вычищаемые строки, и в истории им не место.

- `replacements.txt` — для `--replace-text` и `--replace-message`. Что заменяет: цитаты встречи в `benchmark.md` (имена коллег и клиентов, темы) → описания ошибок распознавания без содержания; цитату с именем коллеги в тикете 11; имя записи встречи → `meeting-86min`; имя пользователя по умолчанию → `Имя Фамилия`; `work-repo` и путь к нему → `work-repo` / `~/src/work-repo`; ссылку на `amanu-research.md` → ссылку на amanu; почту в CLAUDE.md → noreply.
- `mailmap` — автор `Vladimir Seregin <9004182+heaviss@users.noreply.github.com>` (id аккаунта `heaviss` — 9004182).
- Описание машины (Ryzen 5 5600H, память, PipeWire) оставляем: это контекст замеров, не личные данные. Термины-ошибки «жиру», «GidLbа» и склейки тоже оставляем.

Пробный прогон на клоне:

```
uvx git-filter-repo --replace-text .git/public-release/replacements.txt \
  --replace-message .git/public-release/replacements.txt \
  --mailmap .git/public-release/mailmap --force
```

После него поиск по `git log --all -p` не находит ни одной из вычищаемых строк, все коммиты подписаны noreply, `pytest` на новой вершине проходит (34). Переписываются и локальные ветки `prototype/*`; их по-прежнему не пушим.
