---
type: research
status: closed
assignee: claude
blocked_by: []
---

# Как устроены сессии Claude Code на диске

## Question

Где и в каком формате Claude Code хранит сессии (`~/.claude/projects/…/*.jsonl`): схема строк, как связать сессию с проектом и датой, какой объём на этой машине, как дёшево найти сессии, где упомянут тикет или термин (grep по JSONL, `history.jsonl`, сжатые summary сессий)? Что из этого можно отдать summarizer без утечки секретов из tool-вывода?

## Resolution

Находки: `.scratch/summary-context/research/claude-code-sessions.md` на ветке `research/claude-code-sessions`.

- Сессии: `~/.claude/projects/<cwd с не-alnum → ->/<uuid>.jsonl`, открытый текст, хранятся 30 дней (`cleanupPeriodDays`); промпты ещё и в `~/.claude/history.jsonl` без автоочистки. Формат строк недокументирован; официальное чтение — Agent SDK `list_sessions()` / `get_session_messages()`.
- Проект — поле `cwd` в строках (в ~10% сессий меняется), дата — `timestamp` (UTC). Готовых summary нет: только `ai-title` и редкий `isCompactSummary`.
- Объём здесь 3,2 ГБ, 560 сессий; промпты человека и `text` ассистента — ~1% байтов.
- Поиск: `rg -l` по всему — 1–2 с, но много ложных совпадений в выводе инструментов; искать по промптам человека, разбирать `jq`.
- Секреты (приватные ключи, токены, `user:pass@` в URL) живут в `tool_result`, `toolUseResult`, `tool_use.input`, `api-request*`. Поэтому summarizer получает только выжимку (заголовок, промпты, `text` ассистента, `cwd`, `gitBranch`, даты) через фильтр секретов; сырой JSONL и `Read` по `~/.claude/projects` не даём.
