---
type: task
status: open
assignee:
blocked_by: [02, 03]
---

# Замер токенов и качества по моделям и effort

## Question

Сколько токенов, $ и времени тратит summary на своих встречах для матрицы модель (Opus, Sonnet, Haiku) × effort (по умолчанию, low) с выбранным в [Кто подбирает контекст](03-context-source.md) источником контекста, и насколько хуже результат? Источник — агент над папкой контекста (→ 03); скрипт-основа — `checks/context_source.py` на ветке `prototype/context-source`. Отдельно замерить вклад `<glossary>`: он больше половины stdin. Скрипты в `checks/`, в репо — только агрегаты.
