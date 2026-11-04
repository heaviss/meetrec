---
type: grilling
status: closed
assignee: claude
blocked_by: []
---

# Вызывать transcribe.cpp как CLI или через Python-биндинг

## Question

CLI отдаёт метки токенов только текстом в stdout (`--timestamps token`, один файл), а Python-колесо `transcribe-cpp` с PyPI (CPU + Vulkan, без сборки) отдаёт `Result.tokens` напрямую, но помечено «in development». Что берём, и как это меняет принятое в Notes «transcribe.cpp — подпроцесс»? См. [исследование](research/transcribe-cpp.md).

## Resolution

- Python-биндинг `transcribe-cpp==0.4.1` (+ `transcribe-cpp-native`), версия закреплена; CLI не собираем. Проверен [замером](research/benchmark.md) на 86 мин; метки токенов — `res.tokens` (`t0_ms`, `t1_ms`, `text`). Обновление — вручную, с повтором замера.
- Расшифровка — отдельный процесс на дорожку под `nice -n 19`, его запускает демон: падение ggml/Vulkan не роняет демон, память освобождается после дорожки.
- Сначала `backend="vulkan"`; при ошибке или падении — один повтор на `cpu` с `n_threads=4`; упал и он — встреча в Ошибку, уведомление.
