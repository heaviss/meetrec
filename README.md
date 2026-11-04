# meetrec

Демон для Linux сам пишет ваши звонки и расшифровывает их на машине.

Звонок начинается, когда браузер или Zoom занимает микрофон. Демон пишет две дорожки: `me` — ваш микрофон, `them` — всё, что играет компьютер. Когда звонок кончился, GigaAM-v3 расшифровывает обе дорожки по-русски, а `claude -p` пишет саммари. Звук не уходит с машины, в Claude уходит только текст.

Как устроено и почему — в [SPEC.md](SPEC.md), термины — в [GLOSSARY.md](GLOSSARY.md).

## Что нужно

- Linux с PipeWire и `pactl`, `pw-record`, `notify-send`;
- `uv` и Python 3.14 (`uv python install 3.14`);
- `git` и `g++`: `meetrec setup` собирает LocalVQE;
- `claude` с входом в аккаунт — для саммари.

## Установить

```bash
cd ~/PycharmProjects/meetrec
uv tool install --editable . --python 3.14
meetrec setup
```

`meetrec setup` скачивает модели в `~/.local/share/meetrec/models/`, собирает LocalVQE и включает сервис `systemd --user`. Команду можно запускать повторно: готовые шаги она пропускает.

С `--editable` правка кода подхватывается перезапуском: `systemctl --user restart meetrec`.

## Пользоваться

Ничего делать не нужно: демон сам замечает звонок и шлёт уведомления — запись началась, встреча записана, саммари готово.

Каждая встреча лежит в своей папке `~/Recordings/<ГГГГ-ММ-ДД-ЧЧММ>/`:

| файл | что в нём |
|---|---|
| `summary.md` | итоги, решения, задачи, открытые вопросы |
| `transcript.md` | реплики `me` и `them` с метками времени |
| `me.wav`, `them.wav` | звук, 16 кГц mono |
| `me.clean.wav` | `me` без эха; появляется, только если звук шёл в динамики |
| `me.tokens.tsv`, `them.tokens.tsv` | слова с метками времени, из них собирается транскрипт |
| `meta.json` | статус, приложения, устройства вывода, ошибки |

Встречи короче 2 минут демон удаляет сам.

Команды:

```bash
meetrec status                          # что делает демон, очередь, встречи с ошибкой или без саммари
meetrec redo ~/Recordings/<папка>        # доделать недостающее: расшифровку или саммари
meetrec redo ~/Recordings/<папка> --transcript   # пересобрать transcript.md и саммари без расшифровки
meetrec redo ~/Recordings/<папка> --all  # всё заново
journalctl --user -u meetrec -f         # журнал демона
```

### Настроить

Конфиг необязателен. Значения по умолчанию перечислены в [SPEC.md](SPEC.md#3-конфиг), а свои кладут в `~/.config/meetrec/config.toml`:

```toml
pause_s = 30                      # сколько ждать возврата микрофона, прежде чем закрыть встречу
user_name = "Имя Фамилия"
glossary_repo = "~/src/work-repo"
```

После правки: `systemctl --user restart meetrec`.

## Почистить записи

Каждая встреча — отдельная папка с датой в имени, её можно удалить целиком. Команды ниже трогают только такие папки. Встречу, которая пишется или обрабатывается, не трогайте: её показывает `meetrec status`.

Удалить звук старше 30 дней, текст оставить:

```bash
fd -e wav --changed-before 30d . ~/Recordings/20* -x rm
```

После этого `meetrec redo --transcript` для такой встречи работает, а `redo --all` — уже нет: расшифровывать нечего.

Удалить встречи старше 90 дней целиком:

```bash
fd --type d --max-depth 1 --changed-before 90d '^20' ~/Recordings -x rm -r
```

## Удалить

```bash
systemctl --user disable --now meetrec
rm ~/.config/systemd/user/meetrec.service
systemctl --user daemon-reload
uv tool uninstall meetrec
rm -r ~/.local/share/meetrec ~/.config/meetrec
```

Записи в `~/Recordings` остаются — удалите их сами, если не нужны.
