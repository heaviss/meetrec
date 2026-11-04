# Лицензии зависимостей meetrec

Проверено 2026-11-04 по первичным источникам: метаданные PyPI, файлы LICENSE на GitHub, карточки моделей и API Hugging Face, содержимое колеса `transcribe_cpp_native-0.4.1-…manylinux…x86_64.whl`.

## Компоненты

| Компонент | Как попадает к пользователю | Лицензия | Источник |
|---|---|---|---|
| `transcribe-cpp` 0.4.1 | PyPI, runtime-зависимость | MIT | https://pypi.org/pypi/transcribe-cpp/0.4.1/json (`license_expression: MIT`) |
| `transcribe-cpp-native` 0.4.1 | PyPI, колесо с `libtranscribe.so`, `libggml*.so` (вкл. Vulkan-бэкенд) | MIT; в колесе лежат `LICENSE`, `ggml/LICENSE`, `miniz/LICENSE`, `silero_vad/LICENSE` | https://pypi.org/pypi/transcribe-cpp-native/0.4.1/json |
| upstream `handy-computer/transcribe.cpp` | исходники колёс | MIT | https://github.com/handy-computer/transcribe.cpp/blob/main/LICENSE |
| ggml (вендорен в transcribe.cpp) | внутри колеса | MIT | https://github.com/handy-computer/transcribe.cpp/blob/main/THIRD-PARTY-LICENSES.md |
| Silero VAD, miniz (вендорены в transcribe.cpp) | внутри колеса | MIT | там же |
| Модель `gigaam-v3-e2e-ctc-Q8_0.gguf` (квантизация GigaAM-v3) | `meetrec setup` скачивает с HF | MIT, унаследована от базовой; в репо есть `LICENSE` и `NOTICE` | https://huggingface.co/handy-computer/gigaam-v3-e2e-ctc-gguf |
| Исходная модель GigaAM-v3 (`ai-sage/GigaAM-v3`) | база для GGUF | MIT | https://huggingface.co/ai-sage/GigaAM-v3 (`License: MIT`) |
| Код GigaAM (Salute / Sber, «GigaChat Team») | не используется напрямую | MIT, © 2024 GigaChat Team | https://github.com/salute-developers/GigaAM/blob/main/LICENSE |
| Код LocalVQE `localai-org/LocalVQE` @ `7f61cd0` | `meetrec setup` клонирует и собирает у пользователя | Apache-2.0 | https://github.com/localai-org/LocalVQE/blob/7f61cd0/LICENSE |
| ggml (сабмодуль LocalVQE, `ggml/vendor/ggml`) | собирается вместе с LocalVQE | MIT | https://github.com/ggml-org/ggml/blob/master/LICENSE |
| Модель `localvqe-v1.4-aec-200K-f32.gguf` (`LocalAI-io/LocalVQE`) | `meetrec setup` скачивает с HF | Apache-2.0; обучена на DNS Challenge (Microsoft, CC BY 4.0) и AEC Challenge | https://huggingface.co/LocalAI-io/LocalVQE |
| Dev-группа: pytest, mypy, wemake-python-styleguide и их транзитивные (flake8, attrs, pygments, packaging…) | только для разработки, в пакет не входят | MIT / BSD / Apache-2.0 / PSF — все пермиссивные | PyPI JSON каждого пакета |
| `claude` CLI | ставит сам пользователь, вызывается как внешний процесс | проприетарный, условия Anthropic | https://www.anthropic.com/legal/consumer-terms |

Копилефта (GPL/LGPL/AGPL) и некоммерческих условий (CC BY-NC, RAIL и т. п.) нет ни у одного компонента.

## Вердикт: MIT можно

- Всё, что meetrec импортирует или вызывает, под MIT или Apache-2.0. Обе лицензии совместимы с MIT для вызывающего кода; Apache-2.0 не требует, чтобы код, который запускает или линкует LocalVQE, был под Apache.
- meetrec не распространяет ни моделей, ни бинарников: колёса ставит `uv` с PyPI, модели и код LocalVQE `meetrec setup` скачивает и собирает на машине пользователя. Поэтому обязанности «приложить текст лицензии и NOTICE» (MIT §1, Apache-2.0 §4) на репозиторий meetrec не ложатся — их исполняют сами источники (в колесе лицензии лежат, в HF-репо GGUF есть `LICENSE` и `NOTICE`, в клоне LocalVQE — `LICENSE`). Это важно: если когда-нибудь meetrec начнёт вкладывать модели или `.so` в свой релиз (Docker-образ, tarball, свой HF-репо), тексты MIT/Apache и NOTICE придётся класть рядом.
- `claude -p` — внешний сервис по аккаунту пользователя, на лицензию кода meetrec не влияет.

## Что написать в README

Юридически обязательного нет; ниже — то, что честно и принято:

1. `LICENSE` в корне с текстом MIT и строкой `Copyright (c) 2026 <автор>`; в README — «Лицензия: MIT».
2. Раздел «Сторонние компоненты» со ссылками и лицензиями:
   - [transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) (MIT, включает ggml, Silero VAD, miniz);
   - [GigaAM-v3](https://huggingface.co/ai-sage/GigaAM-v3) от Salute Developers / Sber (MIT), GGUF-квантизация [handy-computer/gigaam-v3-e2e-ctc-gguf](https://huggingface.co/handy-computer/gigaam-v3-e2e-ctc-gguf);
   - [LocalVQE](https://github.com/localai-org/LocalVQE) (Apache-2.0), модель [LocalAI-io/LocalVQE](https://huggingface.co/LocalAI-io/LocalVQE) (Apache-2.0).
3. Фраза, что `meetrec setup` скачивает модели и код этих проектов с Hugging Face и GitHub, и они распространяются на условиях своих лицензий, а не лицензии meetrec.
4. Что саммари пишет `claude` CLI на условиях Anthropic: текст расшифровки уходит в Anthropic (это уже есть в README, строка 5).
5. По желанию: предупреждение из карточки LocalVQE — модель может глушить крик/плач, не для критичных к безопасности применений. Цитирование статей DeepVQE/GTCRN карточка просит лишь «please cite» — для README не обязательно.
