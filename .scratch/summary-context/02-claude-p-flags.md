---
type: research
status: open
assignee:
blocked_by: []
---

# Что `claude -p` позволяет ограничить и замерить

## Question

Какими флагами `claude -p` (текущая версия на машине и документация) можно: (1) дать только инструменты чтения (`Read`, `Grep`, `Glob`) и ограничить их путями — `recordings_dir` и папкой сессий Claude Code; (2) выбрать модель (`--model` и алиасы) и effort (`--effort` или аналог); (3) получить расход токенов и $ за вызов (`--output-format json`: `usage`, `total_cost_usd`)? Какие текущие цены Opus, Sonnet и Haiku за input, output и cache?
