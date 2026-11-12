---
type: research
status: closed
assignee: claude
blocked_by: []
---

# Что `claude -p` позволяет ограничить и замерить

## Question

Какими флагами `claude -p` (текущая версия на машине и документация) можно: (1) дать только инструменты чтения (`Read`, `Grep`, `Glob`) и ограничить их путями — `recordings_dir` и папкой сессий Claude Code; (2) выбрать модель (`--model` и алиасы) и effort (`--effort` или аналог); (3) получить расход токенов и $ за вызов (`--output-format json`: `usage`, `total_cost_usd`)? Какие текущие цены Opus, Sonnet и Haiku за input, output и cache?

## Resolution

Находки и замер: [research/claude-p-flags.md](research/claude-p-flags.md).

- Только чтение: `--tools Read,Grep,Glob`. MCP этим флагом не отключается: коннекторы claude.ai подключаются посреди прогона, поэтому нужны `--strict-mcp-config` и `--disallowedTools 'mcp__*'`.
- Пути: читать можно cwd и папки из `--add-dir=PATH`, остальное `-p` отклоняет; `--permission-mode dontAsk` фиксирует это явно. Точечно — `Read(//abs/**)` в allow или deny.
- Модель: `--model haiku|sonnet|opus` (сейчас 5.5) или полное имя; effort: `--effort low|medium|high|xhigh|max`, дефолт в Claude Code `medium`.
- Расход: `--output-format json` → `total_cost_usd` (оценка клиента, не счёт), `usage`, `modelUsage`. Пустой вызов стоит ~3,5 тыс. токенов: Haiku $0,0006, Sonnet $0,009, Opus $0,018.
- Цены за 1 млн, вход / выход / чтение кэша / запись 1h: Opus 5.5 — 4 / 20 / 0,20 / 8, Sonnet 5.5 — 2 / 10 / 0,10 / 4, Haiku 5.5 — 0,10 / 0,50 / 0,01 / 0,20 (до 100 тыс. токенов промпта).
