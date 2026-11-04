# План: открыть meetrec

Собран из решений [карты](map.md). Выполняется за одну сессию, шаги по порядку. Каждый пункт ссылается на тикет с подробностями.

## 1. Правки кода (обычные коммиты в `master`)

1. `config.py` (→ 04, 06):
   - `user_name` по умолчанию — полное имя из GECOS (`pwd.getpwuid(os.getuid()).pw_gecos`, до первой запятой), если пусто — логин;
   - `glossary_repo: Path | None = None`;
   - `language: str = "ru"` (`ru` | `en`), путь к модели по языку.
2. `install.py` (→ 02, 05, 06):
   - `MODELS` по языку: GigaAM для `ru`, `parakeet-tdt-0.6b-v2` Q8_0 для `en` (URL и sha256 — в [research/english-models.md](research/english-models.md)); `setup` качает только модель языка из конфига;
   - LocalVQE (модель, клон, сборка) — только при `echo_cancel = true`;
   - `--parallel` вместо `-j6`; удалить `OLD_CACHE` и перенос.
3. `daemon.py`: при старте, если `echo_cancel = true`, а библиотеки или модели LocalVQE нет, — одно уведомление «эхо не подавляется: запустите `meetrec setup`» (→ 02).
4. `asr.py`: модель и `language` по языку встречи вместо зашитого `"ru"`; у Parakeet ведущий пробел в `Token.text` заменить на `▁` (→ 05).
5. Язык встречи пишется в `meta.json` при закрытии; `meetrec redo --language en <встреча>` меняет его и пересчитывает всё (→ 06).
6. `summary.py` и `prompt.md` (→ 04, 06):
   - `prompt.md` по-английски, со строкой «write the summary in {language}»;
   - без `glossary_repo` — без словаря;
   - нет `claude` в `PATH` — саммари пропускается, `meta.json` это отмечает, `status` не считает встречу недоделанной.
7. Тесты: `words()` на токенах Parakeet; умолчание `user_name`; пропуск саммари без `claude`; выбор моделей в `setup`.
8. Документы:
   - `wayfinder/SPEC.md`: конфиг (`language`, `glossary_repo`, `user_name`), установка, языки, пропуск саммари;
   - `README.md` по-английски по [тикету 04](04-readme.md);
   - `LICENSE`: MIT, `Copyright (c) 2026 Vladimir Seregin`;
   - `CLAUDE.md`: убрать почту и личные правила пуша, добавить установку `--editable` из клона;
   - тикеты 11 и 12 в `wayfinder/`: ссылки на `checks/` → «скрипты удалены, есть в истории git».
9. Проверки: `uv run pytest -q`, `uv run mypy meetrec tests`, `uv run flake8 meetrec tests`, `uvx ruff check -q meetrec tests`, `uvx ruff format --check -q meetrec tests`.
10. Живая проверка: `meetrec setup` с `language = "en"`, затем `redo --language en` на записи с английской речью; замерить пик памяти Parakeet (не измерен).

## 2. Переписать историю (→ 03)

1. Резервная копия: `git clone --mirror ~/PycharmProjects/meetrec ~/meetrec-backup.git`.
2. В репозитории:
   ```
   uvx git-filter-repo --replace-text .git/public-release/replacements.txt \
     --replace-message .git/public-release/replacements.txt \
     --mailmap .git/public-release/mailmap --force
   git remote add origin git@github.com:heaviss/meetrec.git
   git config user.email 9004182+heaviss@users.noreply.github.com
   ```
3. Проверить: `git log --all -p --format='%an <%ae>%n%B'` не содержит строк из `replacements.txt`; тесты проходят.
4. `git ls-remote origin`: на GitHub только `master`.
5. **Только после явного «да» пользователя:** `git push --force origin master`. Ветки `prototype/*` не пушить.

## 3. Открыть

1. Пользователь в GitHub: Settings → Change visibility → Public; описание и темы (`linux`, `pipewire`, `speech-recognition`, `meeting-notes`).
2. Через неделю удалить `~/meetrec-backup.git` и `.git/public-release/`.
