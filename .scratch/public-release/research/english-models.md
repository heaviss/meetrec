# Модели для английской речи в transcribe-cpp 0.4.1

Тикет: [05-english-models.md](../05-english-models.md). Проверено 2026-11-04.

Источники:

- Тег `v0.4.1` апстрима (коммит `4d7c1cce`): [README](https://github.com/handy-computer/transcribe.cpp/blob/v0.4.1/README.md), [`catalog/*.json`](https://github.com/handy-computer/transcribe.cpp/tree/v0.4.1/catalog), [`docs/models/parakeet.md`](https://github.com/handy-computer/transcribe.cpp/blob/v0.4.1/docs/models/parakeet.md), [`src/arch/parakeet/model.cpp`](https://github.com/handy-computer/transcribe.cpp/blob/v0.4.1/src/arch/parakeet/model.cpp), [`src/arch/gigaam/model.cpp`](https://github.com/handy-computer/transcribe.cpp/blob/v0.4.1/src/arch/gigaam/model.cpp).
- Установленное колесо `transcribe-cpp` 0.4.1 в `~/.local/share/uv/tools/meetrec`: в `libtranscribe.so` собраны все семейства из README.
- Карточки моделей на HF, ссылки в таблице.
- Свой прогон на этой машине, см. «Замер».

## Модели

Колесо 0.4.1 умеет 16 семейств ASR. Здесь только те, что знают английский. Колонки:

- Размер — файл Q8_0 из каталога.
- WER — LibriSpeech test-clean на Q8_0, из каталога.
- Скорость — xRT `dots` на Q8_0 на `ryzen-4750u`, из каталога: CPU / Vulkan. Ryzen 7 4750U — Zen 2 с Vega, как наш 5600H. Для GigaAM в каталоге нет замера на этой машине. Сравнение с GigaAM на одном файле — в разделе «Замер».
- Метки — самая мелкая гранулярность, которую отдаёт `run(timestamps=...)`. meetrec нужны `token` или `word`.

| Модель | Параметры, Q8_0 | Лицензия | Языки, автоопределение | Пунктуация | Метки | WER | CPU / Vulkan |
|---|---|---|---|---|---|---:|---:|
| [`parakeet-tdt-0.6b-v2`](https://huggingface.co/handy-computer/parakeet-tdt-0.6b-v2-gguf) | 618M, 730 МБ | CC-BY-4.0 | en | да, всегда | token, плюс `words` | 1,69 % | 12,7× / 28,4× |
| [`parakeet-ultra`](https://huggingface.co/handy-computer/parakeet-ultra-gguf) (дообученная v3) | 627M, 740 МБ | CC-BY-4.0 | 25 европейских, вкл. ru; есть | да | token | 1,80 % | 11,6× / 21,8× |
| [`parakeet-tdt-0.6b-v3`](https://huggingface.co/handy-computer/parakeet-tdt-0.6b-v3-gguf) | 627M, 740 МБ | CC-BY-4.0 | 25 европейских, вкл. ru; есть | да | token | 1,94 % | 12,2× / 25,8× |
| `parakeet-tdt-1.1b` / `rnnt-1.1b` | 1,1B, 1,27 ГБ | CC-BY-4.0 | en | нет данных | token | 1,38 / 1,46 % | 7,8× / 17,0× |
| `parakeet-tdt_ctc-110m` | 114M, 135 МБ | CC-BY-4.0 | en | нет данных | token | 2,43 % | 44,7× / 75,6× |
| `nemotron-speech-streaming-en-0.6b` | 618M, 730 МБ | other (NVIDIA) | en | нет данных | token | 2,31 % | 12,3× / 28,3× |
| `whisper-large-v3-turbo` | 809M, 886 МБ | MIT | 100; есть | да | только segment | 2,01 % | 1,7× / 3,7× |
| `whisper-small.en` / `base.en` | 242M / 73M | Apache-2.0 | en | да | только segment | 3,09 / 4,16 % | 7,0× / 13,5×; 22,5× / 34,8× |
| `canary-1b-flash` / `canary-180m-flash` | 890M / 189M | CC-BY-4.0 | en, de, es, fr | да | нет | 1,62 / 1,93 % | 7,6× / 15,1×; 18,3× / 30,4× |
| `canary-1b-v2` | 980M, 1,14 ГБ | CC-BY-4.0 | 25; нет | да | нет | 1,91 % | 7,1× / 13,8× |
| `granite-speech-5.0-470m-turboctc` | 473M, 506 МБ | Apache-2.0 | en | нет данных | нет | 1,33 % | 16,6× / 27,0× |
| `qwen3-asr-0.6b` | 782M, 850 МБ | Apache-2.0 | 30; есть | да | нет | 2,11 % | 4,7× / 8,7× |
| `moonshine-*` | 27–266M | MIT | en | да | нет | 2,2–4,6 % | — |
| Cohere, Voxtral, Granite 4.x, Canary-Qwen, Fun-ASR | 0,8–24B, 0,9–26 ГБ | Apache-2.0 / CC-BY / other | разные | да | нет, кроме `granite-speech-4.1-2b-plus` (word) | 1,3–2,1 % | 0,6–5× |
| для сравнения: `gigaam-v3-e2e-ctc` | 221M, 272 МБ | MIT | ru; нет | да | token | — | см. «Замер» |

Метки токенов или слов отдают только Parakeet, Nemotron streaming, MedASR, GigaAM и `granite-speech-4.1-2b-plus`. У Whisper максимум `segment`: `run(timestamps="token")` на `whisper-tiny.en` падает с `UnsupportedRequest: unsupported timestamp granularity`. Canary, Qwen3, Cohere и Voxtral меток не отдают вообще (`capabilities.timestamps.supported: false` в каталоге).

Пунктуация у Parakeet v2 и v3 встроенная, выключить её нельзя: `model.supports("pnc") == False`. Карточка [nvidia/parakeet-tdt-0.6b-v2](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2): «Automatic punctuation and capitalization», «Accurate word-level timestamp predictions». Ровно так же сказано в карточке [v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3).

Определение языка:

- Parakeet v3, `parakeet-ultra` и `orukeet` определяют язык сами. Подсказку `language` они принимают, но вывод от неё не меняется (`docs/models/parakeet.md`, Capabilities). Там же есть предупреждение: «can drift into English on accented spontaneous speech».
- Whisper, Qwen3 и Voxtral тоже умеют определять язык, но меток токенов у них нет.
- Отдельная модель [`lang-id-voxlingua107-ecapa`](https://huggingface.co/handy-computer/lang-id-voxlingua107-ecapa-gguf) весит 27 МБ, лицензия Apache-2.0. Через `model.langid_session().run(pcm, allowed=["ru", "en"])` она отдаёт только язык. Этот вариант для тикета 06.

Длинные записи: у всех Parakeet в каталоге `long_form_strategy: chunked-unbounded`. Внимание локальное, окно ±20,5 с, поэтому многочасовые записи влезают в память, и время растёт линейно (`docs/models/parakeet.md`, Long-form audio). Это тот же режим, что у GigaAM.

## Замер

Сэмпл `samples/dots-full.wav` из апстрима: 305,9 с английской речи. Колесо 0.4.1, `session.run(..., timestamps="token")`. На CPU 4 потока, как в `asr.py`. Машина была занята: свободно ~4 ГиБ, поэтому абсолютные числа ниже, чем в [benchmark.md](../../../wayfinder/research/benchmark.md). Важно соотношение, а не абсолютные цифры.

| Модель | CPU, 4 потока | Vulkan |
|---|---:|---:|
| `parakeet-tdt-0.6b-v2-Q4_K_M` | 29,0 с, 10,6× | 15,8 с, 19,3× |
| `gigaam-v3-e2e-ctc-Q8_0` (тот же файл, `language="ru"`) | 26,0 с, 11,8× | 14,1 с, 21,6× |

Parakeet v2 медленнее GigaAM примерно на 10 %. Значит, час дорожки займёт ~2–2,5 мин на Vulkan и ~5 мин на CPU. Решение «расшифровывать сразу» из benchmark.md остаётся в силе. По каталогу Q8_0 на CPU не медленнее Q4_K_M: 12,7× против 12,5×.

Что отдаёт `run` на `jfk.wav`:

- `tokens`: `(240, 560, ' And')`, `(560, 800, ' so')`, `(800, 960, ',')`, `(1280, 1360, ' fe')`, `(1360, 1520, 'll')`…
- `words`: `(240, 560, 'And')`, `(560, 960, 'so,')`, `(1280, 1680, 'fellow')`…
- текст: «And so, my fellow Americans, ask not what your country can do for you, ask what you can do for your country.»

Модели скачаны в scratchpad и после прогона удалены.

## Рекомендация

**`parakeet-tdt-0.6b-v2`, Q8_0, 730 МБ** ([GGUF](https://huggingface.co/handy-computer/parakeet-tdt-0.6b-v2-gguf), sha256 `f0d0e99cebb6d3b83f1f7069b82b5d3c2e39a54545b0da039cb4bafd9c4e5caa` по HF API).

- Это выбор апстрима по умолчанию для английского («English transcription → `parakeet-tdt-0.6b-v2`. The default pick», `docs/models/parakeet.md`).
- Лучший WER среди моделей ~0,6B с метками токенов. Пунктуация и регистр есть.
- Скорость на уровне GigaAM, работает на CPU и Vulkan без NVIDIA.
- Лицензия CC-BY-4.0 разрешает коммерческое использование с атрибуцией. Модель скачивает `meetrec setup`, в репозиторий она не входит, поэтому вывод из [dependency-licenses.md](dependency-licenses.md) не меняется. Атрибуцию стоит указать в README.

Альтернатива для смешанных встреч — `parakeet-ultra`: один файл на 25 языков с автоопределением. Для русского её не брать: GigaAM на русском сильнее, а v3 может уходить в английский на акцентной речи.

Не подходят:

- Whisper — только сегментные метки, к тому же на порядок медленнее.
- Canary, Granite 5, Qwen3 — без меток.
- Nemotron streaming — лицензия other, WER хуже.

## Что меняется в `asr.py`

1. **Модель по языку.** Вместо `cfg.gigaam_model` нужна таблица `language → (файл, URL, sha256)`: `ru` → GigaAM, `en` → `parakeet-tdt-0.6b-v2-Q8_0.gguf`. Новая запись в `install.MODELS`, путь в `Config`. Что именно качает `setup`, решает тикет 06.
2. **`language=`.** Передавать язык встречи (`"en"`) вместо зашитого `"ru"`. Parakeet v2 принимает `"en"`. Если передать `None`, тоже работает.
3. **Граница слова в токенах — обязательная правка.** GigaAM кладёт в `Token.text` сырой SentencePiece-кусок с `▁`: в `gigaam/model.cpp` стоит `te.text = gm->tok.token(...)`. Parakeet кладёт декодированный фрагмент, где `▁` уже заменён на пробел: в `parakeet/model.cpp` стоит `te.text = tok.decode(&rt.id, 1)`. `transcript.words()` склеивает слова по `WORD_START = "▁"`, поэтому на Parakeet вся запись слилась бы в одно «слово», и паузы между фразами перестали бы работать. Минимальная правка в `transcribe_track` — привести фрагмент к одному виду:
   ```python
   text = WORD_START + token.text[1:] if token.text.startswith(" ") else token.text
   ```
   Другой путь — писать в TSV `recognized.words`: Parakeet их отдаёт, у каждого слова метки и текст с прилипшей пунктуацией. Но GigaAM `words` не заполняет: на нашем прогоне `words 0`. Тогда пришлось бы держать две ветки, так что нормализация токенов проще.
4. **Пунктуация** у Parakeet идёт отдельными токенами без пробела (`','`). Она приклеивается к предыдущему слову, так что `SENTENCE_END` и разбиение на фразы работают без изменений.
5. **Остальное** остаётся как есть: `Model(path, backend=...)`, `session(n_threads=4)` на CPU, откат Vulkan → CPU, `timestamps="token"`. Не проверено: пиковый RSS Parakeet на часовой дорожке. Модель в 2,7 раза больше GigaAM по весам. Веса отображаются через mmap, но на Vulkan их копия лежит в UMA-памяти. Замерить на первой реальной английской встрече.
