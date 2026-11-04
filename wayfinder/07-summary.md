---
type: prototype
status: closed
assignee: claude
blocked_by: [06]
---

# Что пишет summary.md и с каким промптом

## Question

Какие разделы у `summary.md` (итоги, решения, задачи с владельцами), какой промпт и вызов `claude -p` (модель, флаги, длинные транскрипты), что делать, если `claude` недоступен?

Вход от [Как выглядит transcript.md](06-transcript-format.md): транскрипт без чистки, термины сломаны. Словарь терминов для промпта пока — `GLOSSARY-MAP.md` и `GLOSSARY.md`-файлы `~/src/work-repo`: как их подавать (целиком, выжимкой) и что делать со встречами не про рабочий репозиторий.

## Resolution

Прототип: ветка `prototype/summary` (`prototypes/summary_prompt_PROTOTYPE.md`, `summarize_PROTOTYPE.sh`); прогон на 86 мин встречи — по ~38 с, саммари со словарём и без лежат в `~/Recordings/bench/summary-{glossary,plain}.md`.

- Разделы: `# тема`, «Кратко» (3–5 пунктов), «Решения» и «Задачи» (`- [ ] что — кто — срок [ЧЧ:ММ:СС]`) с метками времени, «Открытые вопросы». Промпт — как в прототипе.
- Словарь: все `GLOSSARY-MAP.md` и `*GLOSSARY.md` из work-repo (`git ls-files`, ~120 КБ) в `<glossary>` на каждой встрече; путь к репозиторию — в конфиге. Со словарём восстановились Payriff, INXY, Revolut, `payment_received` (без него — «PimRift»); времени не добавляет.
- В промпте: «`me` — Имя Фамилия», его задачи помечаются «— я»; имя — в конфиге.
- Вызов: `claude -p --no-session-persistence --tools "" --setting-sources project --system-prompt-file <prompt>` из временной папки, транскрипт в stdin, модель по умолчанию.
- Если `claude` упал: встреча всё равно Готова с транскриптом, в `meta.json` — саммари не сделано, уведомление; повтор — ручной командой.
