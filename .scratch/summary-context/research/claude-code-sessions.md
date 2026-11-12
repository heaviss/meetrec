# Сессии Claude Code на диске

Тикет: [01-claude-code-sessions.md](../01-claude-code-sessions.md). Проверено 2026-11-12 на Claude Code 2.1.322.

Источники:

- Документация: [Explore the .claude directory → Application data](https://code.claude.com/docs/en/claude-directory#application-data), [Data usage → Data retention](https://code.claude.com/docs/en/data-usage#data-retention), [Agent SDK: Work with sessions](https://code.claude.com/docs/en/agent-sdk/sessions), [Agent SDK: Python reference](https://code.claude.com/docs/en/agent-sdk/python) (`list_sessions`, `get_session_messages`).
- Осмотр `~/.claude` на этой машине: ключи, типы строк, размеры, счётчики. Текст сообщений, пути и имена других проектов сюда не попали.

## Где лежит

| Путь под `~/.claude/` | Что внутри | Срок |
|---|---|---|
| `projects/<project>/<session-uuid>.jsonl` | Транскрипт: сообщения, вызовы инструментов, их вывод, системный промпт, определения инструментов, параметры запросов | `cleanupPeriodDays`, по умолчанию 30 дней |
| `projects/<project>/<session-uuid>/subagents/agent-<id>.jsonl` и `.meta.json` | Транскрипты субагентов в том же формате; `meta.json` — `agentType`, `description`, `worktreePath` и т. п. | вместе с родителем |
| `projects/<project>/<session-uuid>/tool-results/` | Крупный вывод инструментов, вынесенный в отдельные файлы | вместе с родителем |
| `projects/<project>/memory/` | Auto memory | не чистится |
| `history.jsonl` | Набранные промпты для стрелки вверх и `Ctrl+R` | хранится, пока не удалишь |

Имя `<project>` — абсолютный `cwd`, в котором каждый символ кроме букв и цифр заменён на `-`: `/home/u/proj` → `-home-u-proj`. Имя длиннее 200 символов обрезается и получает хеш. Обратное преобразование неоднозначно, поэтому проект надёжнее брать из поля `cwd` в строках. `CLAUDE_CONFIG_DIR` переносит всё дерево.

Документация прямо предупреждает: «These files are plaintext. Anything that passes through a tool is written to a transcript on disk: file contents, command output, pasted text.» и «If a tool reads a `.env` file or a command prints a credential, that value is written to `projects/<project>/<session>.jsonl`.»

Формат строк JSONL документация не описывает. Официальный интерфейс чтения — Agent SDK: `list_sessions()` → `SDKSessionInfo` (`session_id`, `summary`, `custom_title`, `first_prompt`, `cwd`, `git_branch`, `created_at`, `last_modified`, `file_size`, `tag`) и `get_session_messages()` → `SessionMessage` (`type` `user`/`assistant`, сырой `message`). Схема ниже получена осмотром файлов и может меняться между версиями.

## Объём на этой машине

- `projects/`: 3,2 ГБ. 8 каталогов проектов, 560 основных транскриптов, 2187 транскриптов субагентов.
- Основные транскрипты весят 0,92 ГБ, субагенты 1,9 ГБ, `tool-results/` 0,44 ГБ.
- Размер основного транскрипта: медиана ~0,76 МБ, максимум 57 МБ.
- Один проект держит 545 из 560 сессий и 3,1 ГБ.
- Самая старая сессия — 2026-10-13, ровно 30 дней назад: работает очистка по умолчанию.
- `history.jsonl`: 1,8 МБ, 5398 строк с 2026-05-05, 9 разных проектов. Его очистка не трогает.

## Схема строки транскрипта

Каждая строка — JSON-объект с полем `type`. Распределение по всем основным транскриптам:

| `type` | Строк | Что это |
|---|---|---|
| `assistant` | 44 363 | Ответ модели |
| `user` | 30 355 | Промпт человека или результат инструмента |
| `attachment` | 29 947 | Инъекции харнесса: напоминания, вывод хуков, список skills, окружение |
| `api-request`, `api-request-blob`, `api-request-shape` | ~31 000 | Что ушло в API: системный промпт, инструменты, параметры |
| `last-prompt`, `ai-title`, `custom-title` | ~20 000 | Последний промпт, автозаголовок, ручной заголовок сессии |
| `system` | 3 757 | Служебные события: `turn_duration`, `away_summary`, `compact_boundary` и др. |
| прочие | | `mode`, `permission-mode`, `queue-operation`, `tools-used`, `pr-link`, `file-history-snapshot`, `cost-state`, `agent-name` и др. |

Общие поля строк `user`, `assistant`, `system`, `attachment`: `uuid`, `parentUuid`, `sessionId`, `timestamp` (ISO 8601, UTC), `cwd`, `gitBranch`, `version`, `isSidechain`, `entrypoint`, `userType`. У `assistant` ещё `requestId`, `requestedModel`, `effort`; `message` — объект Messages API с `model`, `content`, `usage`, `stop_reason`.

Синтетический пример, ключи сокращены:

```json
{"type":"user","sessionId":"00000000-0000-4000-8000-000000000000","timestamp":"2026-11-01T10:00:00.000Z","cwd":"/home/u/proj","gitBranch":"main","message":{"role":"user","content":"Почини ABC-123"}}
{"type":"assistant","sessionId":"00000000-…","message":{"role":"assistant","model":"claude-…","content":[{"type":"thinking","thinking":"…"},{"type":"tool_use","id":"toolu_1","name":"Bash","input":{"command":"pytest"}}]}}
{"type":"user","sessionId":"00000000-…","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_1","content":"…"}]},"toolUseResult":{"stdout":"…","stderr":"","interrupted":false}}
{"type":"ai-title","sessionId":"00000000-…","aiTitle":"Починить ABC-123"}
```

### Где текст, а где вывод инструментов

| Поле | Что внутри | Доля байтов в выборке 200 файлов |
|---|---|---|
| `user` с `message.content` строкой | Промпт человека. Флаг `isMeta: true` помечает служебные вставки, `isCompactSummary: true` — пересказ после сжатия | 0,3 % |
| `assistant` → блоки `text` | Ответ модели человеку | 0,4 % |
| `assistant` → блоки `thinking` | Рассуждения модели | 3,0 % |
| `assistant` → блоки `tool_use.input` | Команды и аргументы инструментов | 2,2 % |
| `user` → блоки `tool_result` | Вывод инструментов, который видела модель | 10,2 % |
| `toolUseResult` на той же строке | Структурный дубль вывода: у Bash `stdout`/`stderr`, у Write и Edit — `originalFile`, то есть файл целиком | 13,6 % |
| `user` → блоки `text` в массиве | Вставки skills, команд и харнесса | 2,4 % |
| `attachment`, `api-request*` | Харнесс и тела запросов к API | ~66 % |

Разговор людей и модели — промпты и `text` ассистента — занимает около 1 % транскрипта. Остальное — вывод инструментов и служебные строки.

## Сессия → проект и дата

- Проект: поле `cwd`. В 268 из 300 проверенных сессий `cwd` один. В остальных их 2–5: сессия переходила в worktree или подкаталог. Каталог в `projects/` даёт лишь стартовый `cwd`.
- Дата: первый и последний `timestamp` в файле. `mtime` файла — время последней записи, это дешёвый фильтр «сессии за последние N дней».
- Заголовок: последняя строка `custom-title`, иначе `ai-title`. Агрегаты то же самое дают через `list_sessions()` в Agent SDK.
- `history.jsonl`: ключи `display` (текст промпта), `pastedContents`, `project` (абсолютный путь), `sessionId`, `timestamp` (мс от эпохи). Это самый дешёвый индекс «что я просил и где», и он живёт дольше транскриптов.

## Сжатые summary

- Отдельного файла с summary сессии нет. Строк `type: "summary"` в текущей версии нет вовсе.
- После сжатия контекста в транскрипт пишется `system` с `subtype: "compact_boundary"` и `compactMetadata` (`trigger`, `preTokens`, `postTokens`), а следом `user` с `isCompactSummary: true` — пересказ разговора строкой. Встречается редко: 1 раз на 200 файлов выборки.
- `system` с `subtype: "away_summary"` — краткий пересказ для вернувшегося пользователя.
- `ai-title` — однострочный заголовок, есть почти в каждой сессии.

## Как дёшево найти упоминание тикета или термина

`rg` по всем 3,2 ГБ укладывается в 1–2 секунды на тёплом кэше:

```bash
# сессии, где встречается ключ
rg -l -F 'ABC-123' -g '*.jsonl' ~/.claude/projects
# только промпты человека: content строкой сразу за role
rg -l '"role":"user","content":"[^"]*ABC-123' -g '*.jsonl' ~/.claude/projects
# промпты из history.jsonl, включая сессии старше 30 дней
rg -F 'ABC-123' ~/.claude/history.jsonl | jq -r '[.timestamp, .project, .sessionId] | @tsv'
```

Голый `rg -l` даёт много ложных совпадений: ключ найдётся в `tool_result`, `attachment` и `api-request`, если его показал `git log`, CLAUDE.md или skill. Термин `pytest`, например, нашёлся в 2694 файлах, а в промптах человека — в 726. Надёжнее найти файлы через `rg -l`, а затем разобрать их `jq` и оставить только `user` со строковым `content` без `isMeta`, блоки `text` у `assistant`, `ai-title` и `custom-title`.

Подкаталоги `subagents/` имеет смысл исключать (`-g '!**/subagents/**'`): там две трети объёма, а промптов человека нет.

## Риск: секреты в выводе инструментов

Поиск шаблонов по всем JSONL дал только число файлов, совпадения не открывались. Часть — заглушки и примеры:

| Шаблон | Файлов | Где совпадения |
|---|---|---|
| `BEGIN … PRIVATE KEY` | 122 | `tool_result`, `toolUseResult`, `api-request-blob` |
| JWT `eyJ….eyJ` | 27 | `tool_result`, `toolUseResult`, `tool_use.input` |
| `Bearer <длинный токен>` | 27 | `tool_result`, `toolUseResult`, `tool_use.input` |
| URL с `user:pass@` | 1881 | в основном `api-request`, `attachment`; 8 промптов |
| `password=`, `api_key=`, `token:` с длинным значением | 1502 | не разбиралось |
| `sk-ant-…`, `AKIA…`, `ghp_…` | 0 | |

Выводы:

- Секреты почти целиком сидят в `tool_result`, `toolUseResult`, `tool_use.input`, `api-request*` и `attachment`. Там же лежат дампы окружения, файлы `.env`, вывод SQL и содержимое чужих файлов.
- Промпты и `text` ассистента чище, но не стерильны: человек вставляет токены в промпт, а модель цитирует вывод.
- `toolUseResult` у Write и Edit хранит файл целиком в `originalFile`. Это заметный источник чужого кода и конфигов.
- `history.jsonl` с `pastedContents` несёт вставленный текст и тем же риском.

Для summarizer безопаснее отдавать не сырой JSONL, а выжимку: `ai-title` или `custom-title`, промпты человека без `isMeta`, блоки `text` ассистента, `cwd`, `gitBranch`, первый и последний `timestamp`. Перед отправкой стоит прогнать её через редактор секретов по шаблонам выше. `thinking`, `tool_use`, `tool_result`, `toolUseResult`, `attachment` и `api-request*` выбрасывать целиком. Бонус: выжимка в ~100 раз меньше файла.

Отдать summarizer `Read` по `~/.claude/projects` хуже: модель прочитает сырой вывод инструментов, а транскрипт встречи — недоверенный вход, через который prompt injection попросит найти и пересказать секрет.
