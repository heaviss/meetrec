---
type: research
status: closed
assignee: claude
blocked_by: []
---

# Почему система не замечает подключение наушников

## Question

На этой машине система иногда не замечает подключённые наушники, и их приходится размьючивать через `alsamixer`. Почему так происходит (кодек HDA, jack detection, auto-mute, профиль PipeWire/WirePlumber), как это починить или обойти, и как это влияет на запись: на какой sink и source в этот момент смотрят дорожки `me` и `them`, и может ли демон это заметить?

## Resolution

Вероятная причина — runtime PM контроллера AMD (`power_save=1`, кодек ALC256 спит 83 % времени и полностью обесточивается). Событие о подключении джека теряется во сне, а опрос джека выключен (`jackpoll_ms=0`). Квирка для `1d72:2019` в ядре нет, а патч `hda-alc256-jack.fw` от 26 мая на PM не влияет. Без джека UCM выключает `Headphone Playback Switch`, отсюда `alsamixer`. Предложение — `jackpoll_ms=,1000` в `alsa-base.conf`; при следующем сбое запустить проверку, она отличит потерянное событие от неверного presence detect.

На meetrec сбой не влияет: `them` пишет monitor того же sink-узла (порты Speaker и Headphones у него общие), `me` — встроенный DMIC. Событий у сбоя нет, поэтому демону нужна общая проверка на тишину в `me`.

Подробно: [research/headphones-detection.md](research/headphones-detection.md).
