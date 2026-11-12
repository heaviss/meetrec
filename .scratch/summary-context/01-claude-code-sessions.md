---
type: research
status: open
assignee:
blocked_by: []
---

# Как устроены сессии Claude Code на диске

## Question

Где и в каком формате Claude Code хранит сессии (`~/.claude/projects/…/*.jsonl`): схема строк, как связать сессию с проектом и датой, какой объём на этой машине, как дёшево найти сессии, где упомянут тикет или термин (grep по JSONL, `history.jsonl`, сжатые summary сессий)? Что из этого можно отдать summarizer без утечки секретов из tool-вывода?
