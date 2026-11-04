# transcribe.cpp + GigaAM-v3 + LocalVQE на Ryzen 5 5600H

Тикет: [02-transcribe-cpp.md](../02-transcribe-cpp.md). Дата: 2026-11-03.

Источники, к которым привязаны ссылки `file:line`:

- **TC**: `github.com/handy-computer/transcribe.cpp` на коммите `5700f127` (main, 2026-10-27; последний тег `v0.4.1`).
  Ссылка на строку: `https://github.com/handy-computer/transcribe.cpp/blob/5700f127e38dd53c4735ea23ef743b4b538eacd4/<file>#L<n>`.
- **VQE**: `github.com/localai-org/LocalVQE` на коммите `7f61cd05` (2026-10-19).
- **AM**: `github.com/gsamat/amanu`, тег `windows-v0.6.6`.
- Карточка GigaAM-v3: <https://huggingface.co/ai-sage/GigaAM-v3>.

## Коротко

- Upstream: `handy-computer/transcribe.cpp`. Windows-amanu собирает его из исходников на теге `v0.1.3` (AM `windows/scripts/Build-LocalRuntime.ps1:10-17`). Сейчас актуальна `0.4.1` (TC `include/transcribe.h:154-156`).
- Сборка на CPU: `cmake -B build && cmake --build build`. По умолчанию собирается Release (TC `CMakeLists.txt:59-60`). Vulkan включается опционально: `-DTRANSCRIBE_VULKAN=ON`.
- Для русского берём `gigaam-v3-e2e-ctc-Q8_0.gguf` (272 МБ, WER 5,53 % на FLEURS-ru). Длинное аудио движок режет на окна сам, лимита по длине нет.
- Готовых сегментов с метками времени у GigaAM нет. Он отдаёт только метки токенов с шагом 40 мс, а слова и фразы собирает вызывающий код.
- На родственном CPU (Ryzen 7 PRO 4750U) расшифровка идёт в 16–20 раз быстрее реального времени, на его Vega через Vulkan — в 33–35 раз.
- LocalVQE в transcribe.cpp не входит. Это отдельная библиотека, и ей нужна дорожка-референс: что играли динамики, то есть наш `them.wav`.

## 1. Сборка: Linux x86_64, AVX2, без CUDA

```bash
# Ubuntu/Debian; libopenblas-dev необязателен, glslc/libvulkan-dev — только для Vulkan
sudo apt install build-essential cmake libvulkan-dev glslc libopenblas-dev
cmake -B build                       # CPU
cmake -B build -DTRANSCRIBE_VULKAN=ON # CPU + Vulkan
cmake --build build
```

- Команды взяты из TC `README.md:97-115`. Бинарь CLI: `build/bin/transcribe-cli` (TC `README.md:191`).
- OpenBLAS ускоряет host-декодер в 10–15 раз, а без него сборка уходит на скалярный путь. tinyBLAS включён по умолчанию (TC `README.md:141-143`). В опциях это `TRANSCRIBE_USE_SYSTEM_BLAS`, по умолчанию ON (TC `CMakeLists.txt:148`).
- Все опции: Vulkan по умолчанию OFF, CUDA и HIP включаются отдельно (TC `CMakeLists.txt:111-157`). HIP требует ROCm 6.1+ и `-DAMDGPU_TARGETS=gfx…` (TC `README.md:129-139`). Для Vega в 5600H (gfx90c) реальный кандидат — Vulkan.
- При сборке из исходников флаги ggml берутся из `GGML_NATIVE` и настраиваются под эту машину, в том числе AVX2. Консервативный режим `TRANSCRIBE_X86_CONSERVATIVE` по умолчанию OFF (TC `CMakeLists.txt:159-177`).
- **Можно не собирать.** На PyPI лежат `transcribe-cpp==0.4.1` и `transcribe-cpp-native==0.4.1` с колесом `manylinux_2_28_x86_64` (проверено через `pypi.org/pypi/transcribe-cpp-native/json`). В колесо входят CPU и модуль Vulkan (TC `bindings/python-native/README.md:14-24`). Оно собрано с `GGML_CPU_ALL_VARIANTS=ON`, то есть набор SIMD-инструкций выбирается при запуске (TC `pyproject.toml:149-155`). Если Vulkan-драйвера нет, колесо тихо уходит на CPU. Python API отдаёт `Result.tokens` с `t0_ms`/`t1_ms` (TC `bindings/python/src/transcribe_cpp/__init__.py:547-553,673-689`). Для демона на `uv` это `uv add transcribe-cpp` вместо cmake и подпроцесса. Оговорка: README биндингов ещё пишет «Status: in development» (TC `bindings/python/README.md:6-7`).
- Windows-amanu собирает с `TRANSCRIBE_BACKEND_DL=ON`, `GGML_CPU_ALL_VARIANTS=ON` и `VULKAN=OFF`. Ещё он патчит CLI, чтобы тот инициализировал бэкенды: в v0.1.3 они загружались только для `--list-devices` (AM `windows/scripts/Build-LocalRuntime.ps1:24-44`, `windows/patches/transcribe-cli-init-backends.patch`). Обычной статической сборке Linux этот патч не нужен.

## 2. Модель GigaAM-v3

| Вариант | Q8_0 | WER FLEURS-ru | Вывод |
|---|---:|---:|---|
| `gigaam-v3-e2e-rnnt` | 274 МБ | 5,35 % | с регистром и пунктуацией, точнее |
| `gigaam-v3-e2e-ctc` | 272 МБ | 5,53 % | с регистром и пунктуацией, быстрее |
| `gigaam-v3-ctc` / `-rnnt` | 272–273 МБ | 8,4 / 8,1 % | строчные буквы без пунктуации |

- Таблица взята из TC `docs/models/gigaam.md:15-46`.
- Формат GGUF, имена по схеме `<slug>-<QUANT>.gguf` (TC `README.md:171-173`).
- Ссылка: `https://huggingface.co/handy-computer/gigaam-v3-e2e-ctc-gguf/resolve/main/gigaam-v3-e2e-ctc-Q8_0.gguf`. HTTP 200, `content-length: 272151136`. Доступны кванты от F32 (884 МБ) до Q4_K_M (182 МБ) с почти одинаковым WER (TC `docs/models/gigaam-v3-e2e-ctc.md:38-47`).
- Upstream: `ai-sage/GigaAM-v3`, лицензия MIT, 220–240M параметров. `e2e_*` «produce punctuated, normalized text directly» (карточка HF, строки 2, 10, 35, 63).
- Windows-amanu качает `gigaam-v3-ctc-Q8_0` без пунктуации (AM `windows/src/Amanu.Core/Processing/LocalModels.cs:24-28`). Для саммари лучше `e2e-ctc`.
- Скорость e2e-rnnt примерно вдвое ниже: 10,6× на CPU 4750U (TC `docs/models/gigaam-v3-e2e-rnnt.md:109-119`).

## 3. Длинное аудио: VAD и чанки

- GigaAM обучен на фразах до ~25 с. Длинный вход кодируется перекрывающимися окнами до 25 с, а кадры энкодера склеиваются в одну последовательность для одного greedy-декода. Цитата: «There is no practical length limit, and the encoder workspace does not grow with input length» (TC `docs/models/gigaam.md:52-58`).
- Окно 625 кадров по 40 мс, по 2 с контекста с каждой стороны (TC `src/arch/gigaam/model.cpp:283-303`). `max_audio_ms = 0` (TC `src/arch/gigaam/model.cpp:123-124`). Ошибок длины у семейства нет (TC `docs/input-limits.md:58-71`).
- Встроенного VAD у GigaAM нет. Upstream-нарезку `transcribe_longform` через PyAnnote не портировали (TC `docs/models/gigaam.md:86-90`, `docs/porting/families/gigaam.md:141`).
- Отдельно есть Silero VAD v6.2 (`silero-vad-v6.2-F32.gguf`, 1 МБ): `transcribe-cli -m silero-vad-v6.2-F32.gguf --vad-threshold 0.6 clip.wav`. Он печатает `segment: i start= end= t0= t1=` (TC `docs/vad.md:1-53`, `examples/cli/vad.cpp:66-79`). Параметр `max_speech_ms` режет длинную речь по паузе, но есть только в C/Python API (TC `docs/vad.md:46-53`).
- CLI принимает только WAV 16 кГц, а длину ограничивает 24 часами (TC `examples/common/wav.cpp:19-26,55-61`). Многоканальный WAV сводится в моно (функция `load_wav_mono_16k`).
- amanu на обеих ОС режет GigaAM на куски по 20 с и делает каждый кусок сегментом (AM `windows/src/Amanu.App/TranscriptionServices.cs:96-97,177-202`). С актуальным transcribe.cpp это нужно не для длины, а только чтобы получить сегменты.

## 4. Вывод и метки времени

- `--timestamps auto|none|segment|word|token` (TC `examples/cli/main.cpp:71`). Для GigaAM потолок — `TOKEN` (TC `src/arch/gigaam/capabilities.cpp:21-24`). Модель заполняет только `tokens`, по одному кадру 40 мс на токен (TC `src/arch/gigaam/model.cpp:458-473`). `words` и `segments` она не заполняет: «word- and segment-level timestamps are out of scope» (TC `docs/models/gigaam-v3-e2e-ctc.md:16-18`).
- Режим одного файла печатает в stdout `run: …`, `text: …`, а при `--timestamps token` ещё `tokens: N` и строки `  [  t0 ->   t1] p=0.xxx <piece>` (TC `examples/cli/asr.cpp:866-873,927-936`). Токены — это кусочки SentencePiece. Слова склеиваются по границе `▁`, которая при декоде становится пробелом (TC `src/arch/gigaam/model.cpp:449-456`).
- `-o PATH` пишет только текст (TC `examples/cli/main.cpp:57-58`, `asr.cpp:874`).
- В пакетном режиме `--batch list.txt --batch-jsonl` на каждый файл выходит строка `{"file","text","segments"?,"mel_ms","encode_ms","decode_ms","error"?}`. Токенов в ней нет, а `segments` для GigaAM пуст (TC `examples/cli/asr.cpp:73-99,615-635`). То же отмечено в amanu (AM `windows/src/Amanu.Core/Processing/LocalModels.cs:86-91`).
- SRT, VTT и JSON с токенами CLI не выводит.
- Вывод: сегменты для `transcript.md` собираем сами. Можно, как amanu, взять «кусок 20 с = сегмент» через `--batch-jsonl`. Можно собрать слова из токенов (stdout или `Result.tokens` в Python) и группировать их как amanu-Parakeet: новый сегмент после `.?!`, после паузы больше 1 с или после 60 слов (AM `LocalModels.cs:111-130`).

## 5. Память

- На CPU веса отображаются из GGUF через mmap и живут в page cache, а `--no-mmap` копирует их в память (TC `README.md:200-206`). Для Q8_0 это ~272 МБ.
- Рабочая память энкодера от длины не растёт (TC `docs/models/gigaam.md:56-57`). На хосте же лежат PCM, мел-спектр и склеенный выход энкодера всей записи.
- **Опубликованных цифр RSS для GigaAM нет.** Моя оценка на час одной дорожки, не замер:
  - PCM float32: 16 000 × 3600 × 4 Б ≈ 230 МБ;
  - мел: 64 полосы × 100 кадров/с ≈ 92 МБ (`n_mels=64`, hop 160: TC `src/arch/gigaam/mel.cpp:4`);
  - выход энкодера: 90 000 кадров × 768 × 4 Б ≈ 276 МБ.

  Вместе с весами ≤ ~1 ГБ, в 4,6 ГиБ свободных помещается. Если резать по 20 с или по VAD, хостовая часть ограничена.

## 6. Скорость на CPU

- Опубликованные цифры, `gigaam-v3-e2e-ctc`, AMD Ryzen 7 PRO 4750U с Radeon RENOIR (Zen 2, 8 ядер, iGPU Vega через RADV): CPU Q8_0 даёт 20,1× на 11 с и 16,3× на 33,8 с, Vulkan Q8_0 — 35,1× и 32,7× (TC `docs/models/gigaam-v3-e2e-ctc.md:107-120`). Время считается как mel + encode + decode, среднее из трёх прогонов после прогрева.
- 5600H — Zen 3, 6 ядер, и в нём та же графика Vega 7 (Cezanne). Ориентир: час одной дорожки на CPU займёт ~3–4 мин, на Vulkan ~2 мин. Это экстраполяция, не замер.
- По умолчанию берутся все ядра, а `--threads N` их ограничивает (TC `examples/cli/main.cpp:59`). Если расшифровка идёт во время следующего звонка, ставим `--threads 3–4` и `nice`. amanu ставит процессу приоритет Idle (AM `TranscriptionServices.cs:232`).

## 7. LocalVQE: подавление эха

- В transcribe.cpp его нет. Это отдельный проект `localai-org/LocalVQE` на ggml, Apache-2.0 (VQE `LICENSE`, `README.md:9-14`).
- **Нужен референс**: «Every model needs a far-end reference signal (a loopback of what your speakers play) in addition to the mic» (VQE `README.md:41-42`). Для нас это `them.wav`, monitor системного вывода.
- Модель для нашего случая — `localvqe-v1.4-aec-200K-f32.gguf`, ~3 МБ (HTTP 200, 2 924 224 Б). Она убирает только эхо, а голос и комнату не трогает (VQE `README.md:27-38,55`). Её же берёт amanu (AM `scripts/build-localvqe.sh:9-12`). На Ryzen 9 7900 в 4 потока работает в 19 раз быстрее реального времени, пиковый RSS 17 МиБ (VQE `README.md:31,114-119,151-155`).
- Сборка и запуск офлайн (VQE `README.md:189-217`; на Linux нужен ещё `libsndfile`):

  ```bash
  git clone --recursive https://github.com/localai-org/LocalVQE.git && cd LocalVQE
  cmake -S ggml -B ggml/build -DCMAKE_BUILD_TYPE=Release && cmake --build ggml/build -j$(nproc)
  ./ggml/build/bin/localvqe localvqe-v1.4-aec-200K-f32.gguf --in-wav me.wav them.wav --out-wav me.clean.wav
  ```

  Обе дорожки должны быть 16 кГц моно. Рядом с бинарём должны лежать `libggml-cpu-*.so`.
- Задержку между mic и ref модель оценивает сама: GCC-PHAT, лаг до 16384 сэмплов (~1 с), фиксируется после 3,5 с уверенной оценки (VQE `ggml/daf_frontend.h:4,31-37,68`). Поэтому дорожки нужно подавать с общего нуля. Если позже маршрут сменит задержку, оценка не переподстроится (AM `Sources/amanu/Audio/OfflineEchoAudio.swift:32-36,100-101`).
- amanu на macOS чистит **копию** mic после записи, с системным звуком как референсом. Исходник не меняется (AM `README.md:150-153,481-491`). На Windows LocalVQE нет, вместо него текстовый фильтр дублей `TranscriptEchoFilter` (AM `windows/src/Amanu.App/ProcessingCoordinator.cs:406-407`).

## Команды

```bash
# 1. Сборка (CPU; для Vulkan добавить -DTRANSCRIBE_VULKAN=ON и пакеты libvulkan-dev glslc)
sudo apt install build-essential cmake libopenblas-dev
git clone --depth 1 --branch v0.4.1 https://github.com/handy-computer/transcribe.cpp ~/.local/src/transcribe.cpp
cd ~/.local/src/transcribe.cpp
cmake -B build -DTRANSCRIBE_BUILD_TESTS=OFF
cmake --build build -j

# 2. Модель
mkdir -p ~/.local/share/meetrec/models && cd ~/.local/share/meetrec/models
curl -fLO https://huggingface.co/handy-computer/gigaam-v3-e2e-ctc-gguf/resolve/main/gigaam-v3-e2e-ctc-Q8_0.gguf

# 3. Расшифровка одной дорожки (16 кГц моно WAV), текст + метки токенов
~/.local/src/transcribe.cpp/build/bin/transcribe-cli -q --threads 4 \
  -m ~/.local/share/meetrec/models/gigaam-v3-e2e-ctc-Q8_0.gguf \
  --language ru --timestamps token me.wav

# 3'. Вариант amanu: куски по 20 с → JSONL, один сегмент на кусок
transcribe-cli -m …/gigaam-v3-e2e-ctc-Q8_0.gguf --backend cpu --threads 4 \
  --batch pieces.txt --batch-jsonl --timestamps auto --language ru

# 3''. Без сборки: Python-биндинг с колесом manylinux (CPU + Vulkan)
uv add transcribe-cpp   # Model(path).session(n_threads=4).run(pcm_f32_16k, language="ru").tokens
```

Ключи, кроме `--language ru` для GigaAM, сверены с `examples/cli/main.cpp:39-121`. `--language ru` проверяется по списку языков модели (TC `src/transcribe-asr.cpp:128-139`) и в quick start задан явно (TC `docs/models/gigaam-v3-e2e-ctc.md:78-81`).

## Открытые вопросы

1. **Подпроцесс или Python-биндинг.** Карта выбрала подпроцесс. Но токены CLI отдаёт только в текстовом stdout одного файла, а JSONL их не содержит. Биндинг отдаёт `Result.tokens` напрямую и ставится без сборки, но помечен «in development». Решение нужно до кода.
2. **Сегменты.** Нужно выбрать: «20 с = сегмент», как amanu, или слова из токенов с группировкой по паузам и пунктуации. Второе даёт точнее метки, но это свой код.
3. **Скорость и RSS на 5600H** не измерены. Нужен один прогон часовой записи (`/usr/bin/time -v`), CPU и Vulkan.
4. **Vulkan на Vega** при параллельном звонке (браузер на той же iGPU) не проверен. Также не проверено, держит ли стабильный RADV в системе этот ggml-бэкенд.
5. **LocalVQE.** Если `me` и `them` пишутся одновременно с общего старта, условие выравнивания выполнено. Но если PipeWire меняет устройство вывода посреди звонка (наушники ↔ динамики), фиксированная задержка ломается. В наушниках эха почти нет, так что LocalVQE можно включать опционально.
6. **Пунктуация.** amanu-Windows почему-то взял `gigaam-v3-ctc` без пунктуации. Причина не найдена. Для саммари через `claude -p` предполагаю `e2e-ctc`.
