---
type: grilling
status: open
assignee:
blocked_by: []
---

# Вызывать transcribe.cpp как CLI или через Python-биндинг

## Question

CLI отдаёт метки токенов только текстом в stdout (`--timestamps token`, один файл), а Python-колесо `transcribe-cpp` с PyPI (CPU + Vulkan, без сборки) отдаёт `Result.tokens` напрямую, но помечено «in development». Что берём, и как это меняет принятое в Notes «transcribe.cpp — подпроцесс»? См. [исследование](research/transcribe-cpp.md).
