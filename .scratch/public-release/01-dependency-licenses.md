---
type: research
status: closed
assignee: claude
blocked_by: []
---

# Допускают ли зависимости лицензию MIT

## Question

Под какими лицензиями распространяются то, что ставит или скачивает `meetrec setup`, и Python-зависимости из `uv.lock`: `transcribe-cpp` (колесо и upstream `handy-computer/transcribe.cpp`), модель GigaAM-v3 в формате GGUF, LocalVQE (код `localai-org/LocalVQE` и модель на Hugging Face `LocalAI-io/LocalVQE`). Может ли сам `meetrec` выйти под MIT, и что README обязан указать: атрибуцию, ссылки, условия модели.

## Resolution

Можно MIT. Находки: [research/dependency-licenses.md](research/dependency-licenses.md).

- MIT: `transcribe-cpp` 0.4.1 и upstream (с вендоренными ggml, Silero VAD, miniz), GGUF `handy-computer/gigaam-v3-e2e-ctc-gguf`, `ai-sage/GigaAM-v3`.
- Apache-2.0: код LocalVQE и модель `LocalAI-io/LocalVQE`; модель обучена на DNS Challenge (CC BY 4.0).
- meetrec ничего не распространяет, всё скачивается у пользователя, поэтому тексты чужих лицензий в репозиторий не копируем.
- README: раздел «Сторонние компоненты» со ссылками и лицензиями, фраза «модели скачиваются на условиях своих лицензий», саммари делает `claude` CLI на условиях Anthropic.
