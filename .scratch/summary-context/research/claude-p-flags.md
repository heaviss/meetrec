# Флаги `claude -p`: инструменты, модель, effort, расход

Тикет: [02-claude-p-flags.md](../02-claude-p-flags.md). Проверено 2026-11-12 на Claude Code 2.1.322.

Источники:

- `claude --help` той же версии.
- Документация Claude Code: [CLI reference](https://code.claude.com/docs/en/cli-reference), [Configure permissions](https://code.claude.com/docs/en/permissions), [Permission modes](https://code.claude.com/docs/en/permission-modes), [Model configuration](https://code.claude.com/docs/en/model-config), [Track cost and usage](https://code.claude.com/docs/en/agent-sdk/cost-tracking).
- Цены: [platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing).
- Свои прогоны на синтетических файлах в scratch-папке, см. «Замер». Реальных встреч и сессий в прогонах не было.

## 1. Только чтение и только нужные папки

Рабочая связка, проверена прогоном:

```bash
claude -p --no-session-persistence \
  --setting-sources project \
  --strict-mcp-config --disallowedTools 'mcp__*' \
  --tools Read,Grep,Glob \
  --permission-mode dontAsk \
  --add-dir="$RECORDINGS_DIR" --add-dir="$HOME/.claude/projects/<проект>" \
  --system-prompt-file prompt.md < input.txt
```

Что делает каждый флаг:

- `--tools Read,Grep,Glob` оставляет из встроенных инструментов только эти три. В `init` прогона: `tools: ['Glob', 'Grep', 'Read']`. Bash, Write, Edit, WebFetch, WebSearch, Agent модель не видит вовсе. На Linux набор `default` не содержит `Glob` и `Grep`, их надо назвать явно (CLI reference, `--tools`).
- `--tools` не трогает MCP: «The flag doesn't affect MCP tools; to deny those too, use `--disallowedTools "mcp__*"`» (CLI reference). Проверено: без `--strict-mcp-config` коннекторы claude.ai (Slack, Claude Docs и другие) подключаются асинхронно даже при `--setting-sources project` и в длинном прогоне появляются у модели посреди работы. `--strict-mcp-config` их не подключает вовсе: в debug-логе `Fetched 38 servers`, но ни одного `Successfully connected`. `--disallowedTools 'mcp__*'` убирает MCP-инструменты из контекста, но серверы при этом подключаются. Нужны оба флага: первый не даёт соединиться, второй страхует.
- Читать без запроса можно только рабочие папки: cwd и каждую `--add-dir` («Read-only … No, within the working directory and additional directories», Configure permissions). В `-p` без режима сессия стартует в `default` (Manual), и всё, что требует подтверждения, отклоняется (Permission modes, «Tool calls denied in `claude -p`»). Прогон: Read и Grep по папке вне `--add-dir` попали в `permission_denials`, папка из `--add-dir` читалась.
- `--permission-mode dontAsk` делает то же явно: «Auto-denies every call that would otherwise prompt… File reads in your working directories… still run». Поведение не зависит от того, какой режим станет дефолтным в следующих версиях.
- cwd тоже рабочая папка. meetrec запускает summarizer во временной папке `run_summarizer` (`cwd=workdir`), там лежит только `prompt.md`. Так и оставить.
- Вместо `--add-dir` годится правило: `--allowedTools 'Read(//abs/path/**)'`. Двойной слэш означает абсолютный путь, одиночный — путь от корня проекта (Configure permissions, «How path patterns match»). Проверено: Read, Grep и Glob по такой папке прошли, по соседней получили отказ. Правило `Read(...)` действует и на Grep и Glob. Правила `Grep(path)` и `Glob(path)` не работают, писать нужно `Read(path)`.
- Сузить внутри разрешённой папки помогает deny-правило: `--disallowedTools 'Read(//…/*.wav)'`. Проверено: Read `x.wav` отклонён, Glob не показал `x.wav` в выдаче. Deny всегда сильнее allow: «deny, then ask, then allow».
- Аргумент `--add-dir <directories...>` вариативный и съедает следующий позиционный аргумент. Промпт после него не дойдёт: `Error: Input must be provided…`. Писать `--add-dir=PATH` или подавать промпт через stdin, как делает meetrec.
- `--setting-sources project` не грузит user-настройки с плагинами, скиллами и хуками. Прогон без флага на «hi» стоил 58 702 токена записи в кэш, с флагом — 2 912. Project-настройки берутся из cwd. Во временной папке их нет.
- Флаг `--restricted` (v2.1.248+) запрещает Bash и WebFetch, ограничивает файловые инструменты рабочими папками и не читает user, project и local настройки. Как дополнительная страховка годится, но MCP он не отключает, `--strict-mcp-config` всё равно нужен.
- `--bare` для нас не подходит: принимает только `ANTHROPIC_API_KEY`, OAuth подписки не читает (`claude --help`).

Папка сессий Claude Code — `~/.claude/projects/<путь с дефисами>/*.jsonl`. Её подключают отдельным `--add-dir`. Права на чтение в ней не отличаются от любой другой папки.

## 2. Модель и effort

- `--model` принимает алиас или полное имя: `haiku`, `sonnet`, `opus`, `fable`, `best` = `opus`, `opusplan`. Сейчас на Anthropic API алиасы ведут на `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, `fable` — на Fable 5.2 (Model configuration). В прогоне `modelUsage` назвал ровно эти id. Алиас со временем переезжает на новую модель. Для стабильных замеров лучше полное имя.
- `--effort low|medium|high|xhigh|max` (`claude --help`). Документация ещё называет `ultracode` = `xhigh` плюс режим ultracode. Opus 5.5, Sonnet 5.5 и Haiku 5.5 поддерживают все пять уровней. Если модель уровень не умеет, Claude Code берёт ближайший поддерживаемый уровень ниже.
- Дефолт effort в Claude Code: `medium` у Opus 5.5, Sonnet 5.5, Haiku 5.5 и Fable 5.2 (Model configuration). На уровне API Sonnet 5.5 по умолчанию `high`, но Claude Code шлёт свой дефолт. Чтобы замеры не зависели от дефолтов, задавать `--effort` явно.
- Порядок разрешения: `CLAUDE_CODE_EFFORT_LEVEL` > выбор в сессии > `--effort` > настройки > дефолт модели. Переменная окружения перебивает флаг, это стоит помнить при запуске из systemd-юнита.
- Неизвестное значение не роняет вызов: `Warning: Unknown --effort value 'bogus' — ignoring it and using the default effort.`
- Thinking на Opus 5.5 выключить нельзя, только снизить effort. Токены thinking видны в `usage.output_tokens_details.thinking_tokens` и входят в `output_tokens`.

## 3. Расход за вызов

`--output-format json` отдаёт один объект `type: "result"`. Ответ модели лежит в `result`, расход — в полях ниже.

| Поле | Что внутри |
|---|---|
| `total_cost_usd` | Оценка в $ по прайсу, зашитому в клиент |
| `usage.input_tokens` | Некэшированный вход |
| `usage.cache_creation_input_tokens` | Запись в кэш; разбивка по TTL в `usage.cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens` |
| `usage.cache_read_input_tokens` | Чтение из кэша |
| `usage.output_tokens`, `usage.output_tokens_details.thinking_tokens` | Выход, из него thinking |
| `usage.iterations[]` | То же по каждому запросу к API внутри вызова |
| `modelUsage.<model-id>` | По моделям: `inputTokens`, `outputTokens`, `cacheReadInputTokens`, `cacheCreationInputTokens`, `costUSD`, `costBasis` |
| `num_turns`, `duration_ms`, `duration_api_ms`, `permission_denials`, `is_error`, `subtype` | Служебное; `permission_denials` показывает, куда модель пыталась залезть |

Оговорки из Track cost and usage:

- `total_cost_usd` — оценка клиента, а не счёт: «client-side estimates, not authoritative billing data». На подписке (Pro/Max) деньги за вызов не списываются, поле показывает цену того же объёма по API.
- `usage` не считает субагентов, `total_cost_usd` и `modelUsage` считают. У нас инструмента Agent нет, поля совпадают.
- `--max-budget-usd` останавливает вызов, когда оценка превысит порог, и работает только с `-p`. Порог можно перескочить, нужен запас.
- Сменить `--output-format` на `json` значит поменять парсинг в `run_summarizer`: сейчас он берёт `stdout` как текст.

Замер на синтетике: `echo hi | claude -p --model haiku --output-format json --tools "" --no-session-persistence --setting-sources project`.

| Модель | input | cache write (1h) | cache read | output | `total_cost_usd` |
|---|---:|---:|---:|---:|---:|
| `claude-haiku-5-5` | 2 | 2 912 | 649 | 36 | 0,00061 |
| `claude-sonnet-5-5`, `--effort low` | 2 | 2 088 | 649 | 14 | 0,00856 |
| `claude-opus-5-5`, `--effort low` | 2 | 2 160 | 649 | 15 | 0,01772 |

Пересчёт по таблице цен ниже сходится до цента. Haiku: 2·0,10 + 2 912·0,20 + 649·0,01 + 36·0,50 = 607,09 µ$. Значит, клиент считает запись в кэш по цене 1h: на подписке Claude Code ставит TTL 1 час на запросы основного диалога. Постоянная часть одного вызова — около 3,5 тыс. токенов системного промпта и описаний инструментов. Для Opus это примерно $0,018 ещё до транскрипта.

## 4. Цены API, $ за 1 млн токенов

| Модель | Вход | Запись в кэш 5m | Запись в кэш 1h | Чтение кэша | Выход |
|---|---:|---:|---:|---:|---:|
| Claude Opus 5.5 | 4 | 5 | 8 | 0,20 | 20 |
| Claude Sonnet 5.5 | 2 | 2,50 | 4 | 0,10 | 10 |
| Claude Haiku 5.5, промпт ≤ 100 тыс. | 0,10 | 0,125 | 0,20 | 0,01 | 0,50 |
| Claude Haiku 5.5, промпт > 100 тыс. | 0,50 | 0,625 | 1 | 0,05 | 2,50 |

- Чтение кэша у Opus 5.5 и Sonnet 5.5 стоит 0,05× от входа, у остальных моделей 0,1×.
- У Haiku 5.5 цена зависит от длины промпта. В длину входят и чтение кэша, и запись в кэш. Перешёл порог 100 тыс. — весь запрос оплачивается по верхней строке. У Opus 5.5 и Sonnet 5.5 окно 1 млн по одной цене.
- Batch API вдвое дешевле: Opus 5.5 — 2 / 10, Sonnet 5.5 — 1 / 5, Haiku 5.5 — 0,05 / 0,25 за вход и выход. Через `claude -p` недоступно.
- `inference_geo: "us"` умножает все цены на 1,1. В прогоне было `"global"`.
- Минимальный кэшируемый префикс у всех трёх моделей — 286 токенов.

## Что осталось открытым

- Сколько токенов съедают Read и Grep по реальной папке сессий Claude Code. Это тикет 04-cost-matrix.
- Как ведёт себя `dontAsk`, когда модель упирается в отказ много раз подряд. В коротких прогонах она сообщала об отказе и шла дальше.
