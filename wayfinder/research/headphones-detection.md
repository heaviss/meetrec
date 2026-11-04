# Почему система не замечает подключённые наушники

Тикет: [10-headphones-detection](../10-headphones-detection.md). Машина: RedmiBook Pro 15S (`TIMI RedmiBook Pro 15S`, плата `TM2019`), ядро 7.0.0-42, PipeWire 1.0.5, WirePlumber 0.4.17, `alsa-ucm-conf 1.2.10-1ubuntu5.15`.

Всё снято только чтением, и подключения наушников при снятии не было. Поэтому механизм потери события — **гипотеза**: ниже есть проверка, которая подтвердит её или опровергнет при следующем сбое.

## Коротко

- Звук идёт через аналоговый кодек Realtek ALC256 (карта 1, `hw:Generic_1`, PCI `03:00.6`), а встроенный микрофон — через отдельную карту `acp`. Наушники — пин `0x21`, о подключении ядро сообщает через kcontrol `Headphone Jack`.
- Если `Headphone Jack` остаётся `off`, PipeWire считает порт `[Out] Headphones` недоступным и держит `[Out] Speaker`. UCM при этом выключает `Headphone Playback Switch`. Отсюда и ручное включение в `alsamixer`.
- Вероятная причина — runtime PM. При `power_save=1` кодек и контроллер спят 83 % времени и при этом полностью теряют питание. Событие о подключении (unsolicited event) приходит в спящий кодек и теряется, а опроса джека нет: `jackpoll_ms=0`. Для `1d72:2019` в ядре нет ни квирка кодека, ни записи в power_save denylist.
- Патч `hda-alc256-jack.fw` от 26 мая уже стоит. Он лишь повторяет init-verbs, которые драйвер и так шлёт пину `0x21`, и на PM не влияет. Видимо, поэтому сбой остался.
- Предложение: `jackpoll_ms=,1000` для карты 1. Кодек перестаёт засыпать, и драйвер раз в секунду сам читает состояние джека.
- На meetrec сбой почти не влияет. `them` пишет monitor того же sink-узла, а Speaker и Headphones — порты одного узла, так что запись идёт, даже когда в наушниках тихо. `me` остаётся на цифровом микрофоне. Событий у сбоя нет: сбой и есть отсутствие события, поэтому ловить его стоит не по событиям, а по тишине в записи.

## Что на машине

**Кодек и подсистема** (`head -5 /proc/asound/card1/codec#0`):

```
Codec: Realtek ALC256
Vendor Id: 0x10ec0256
Subsystem Id: 0x1d722019
```

**Конфигурация пинов при загрузке и сейчас.** `cat /sys/class/sound/hwC1D0/init_pin_configs` показывает, что при загрузке BIOS отдал `0x21 0x04211020` (HP-джек) и `0x19 0x04a11040` (mic-джек). Сейчас чтение пина в `/proc/asound/card1/codec#0` даёт другое:

```
Node 0x21 [Pin Complex] ...
  Pincap 0x0001001c: OUT HP EAPD Detect
  Pin Default 0x411111f0: [N/A] Speaker at Ext Rear
  Pin-ctls: 0xc0: OUT HP
  Unsolicited: tag=01, enabled=1
```

Регистр вернулся к заводскому `0x411111f0`, значит кодек после загрузки обесточивался и сбрасывался. Драйвер работает с кэшем `init_pin_configs`, так что само значение безвредно, но доказывает полный сброс. Ядро при загрузке нашло наушники (`journalctl -k -b`):

```
snd_hda_intel 0000:03:00.6: Applying patch firmware 'hda-alc256-jack.fw'
snd_hda_codec_alc269 hdaudioC1D0: autoconfig for ALC256: line_outs=1 (0x14/...) type:speaker
snd_hda_codec_alc269 hdaudioC1D0:    hp_outs=1 (0x21/0x0/0x0/0x0/0x0)
snd_hda_codec_alc269 hdaudioC1D0:      Mic=0x19
```

**Runtime PM.** `/sys/module/snd_hda_intel/parameters/` показывает `power_save=1`, `power_save_controller=Y` и `jackpoll_ms=0,0,…`. По `/sys/bus/hdaudio/devices/hdaudioC1D0/power/` кодек спал 76 840 с из 92 300 с:

```
runtime_status=suspended
runtime_active_time=15466444
runtime_suspended_time=76840913
```

У контроллера `0000:03:00.6` те же цифры. Поверх этого за загрузку было 8 входов в s2idle (`journalctl -b | rg -c 'PM: suspend entry'`).

**Действующий патч.** `/etc/modprobe.d/alsa-base.conf:45-46` и `/lib/firmware/hda-alc256-jack.fw` (26 мая):

```
# Fix for headphones non-detection
options snd_hda_intel patch=,hda-alc256-jack.fw
```
```
[codec]
0x10ec0256 0x1d722019 0

[init_verbs]
0x21 0x708 0x81   # SET_UNSOLICITED_ENABLE, tag 1
0x21 0x707 0xc0   # SET_PIN_WIDGET_CONTROL: OUT+HP
0x21 0x70c 0x02   # SET_EAPD_BTLENABLE: EAPD
```

Тот же тег 01 и те же pin-ctls драйвер выставляет и сам (`Unsolicited: tag=01, enabled=1`, `Pin-ctls: 0xc0`). Патч ничего не добавил к тому, что делает драйвер, и не трогает PM. Прошлой сессии Claude об этом в `~/.claude/projects` не нашлось: упоминание есть только в `history.jsonl` текущей сессии. В `~/obsidian/zettelcasten` тоже ничего нет. Остался только этот патч.

**Состояние сейчас** (`amixer -c 1 contents`, `LC_ALL=C pactl list sinks`):

```
numid=12,iface=CARD,name='Headphone Jack'   : values=off
numid=2,iface=MIXER,name='Headphone Playback Switch' : values=on,on
Simple mixer control 'Auto-Mute Mode',0  Item0: 'Enabled'
```
```
[Out] Speaker: Speaker (type: Speaker, priority: 100, availability unknown)
[Out] Headphones: Headphones (type: Headphones, priority: 200, availability group: Headphone, not available)
Active Port: [Out] Speaker
```

`wpctl status` показывает один sink `52. … Speaker + Headphones` и источники `53. … Headphones Stereo Microphone` и `* 54. … Digital Microphone` (default). В системе нет `hda-verb`, `hdajackretask` и `hda-analyzer` (`which`), а `alsactl` и `alsa-info` есть.

## Почему так происходит

**1. Цепочка от джека до `alsamixer`.**
- Ядро обновляет `Headphone Jack` по unsolicited event пина `0x21` или по опросу (`jackpoll`). На карте 1 опрос выключен: `jackpoll_ms=0`, а описание параметра в ядре говорит `"Ms between polling for jack events (default = 0, using unsol events only)"`. Источник: [intel.c:142-143](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/sound/hda/controllers/intel.c?h=v7.0#n142).
- UCM описывает порт Headphones с `JackControl "Headphone Jack"`, а при отключении устройства выполняет `cset "name='Headphone Playback Switch' off"`. Источник: `/usr/share/alsa/ucm2/HDA/HiFi-analog.conf:103-128`, upstream https://github.com/alsa-project/alsa-ucm-conf/blob/v1.2.10/ucm2/HDA/HiFi-analog.conf.
- Пока джек `off`, ACP в PipeWire держит активным `[Out] Speaker`, и Headphones-устройство выключено, а с ним и `Headphone Playback Switch`. Включение `Headphone` в `alsamixer` открывает усилитель пина в обход PipeWire. Пин и так стоит в `OUT HP`, поэтому звук появляется, но Speaker при этом не глушится: auto-mute ядра тоже срабатывает только по джеку.

**2. Почему джек не обновляется (гипотеза).**
- Контроллер AMD `1022:15e3` идёт с `AZX_DCAPS_PRESET_AMD_SB`, а этот пресет включает `AZX_DCAPS_PM_RUNTIME`. Источник: [intel.c:316-319, 2635-2636](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/sound/hda/controllers/intel.c?h=v7.0#n316).
- Через `power_save` секунд простоя кодек и контроллер засыпают. Kernel docs: «When the device is inactive for a certain time, the device is automatically turned off to save the power» (https://docs.kernel.org/sound/hd-audio/notes.html). Кодек при этом теряет питание: это видно по сбросу `Pin Default` и по 83 % времени во сне.
- Подключение во сне может дойти до ядра только как wake: контроллер перед сном включает `WAKEEN` ([intel.c:1112-1113](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/sound/hda/controllers/intel.c?h=v7.0#n1103)). После пробуждения кодек будится, только если его бит стоит в `STATESTS` или выставлен `forced_resume` ([intel.c:986-1000](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/sound/hda/controllers/intel.c?h=v7.0#n975)). Если обесточенный кодек wake не подаёт, события нет, и `Headphone Jack` остаётся `off`.
- При следующем resume кодека ядро всё же перечитывает джеки (`snd_hda_jack_set_dirty_all` и `snd_hda_jack_report_sync`, [codec.c:2860-2887](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/sound/hda/common/codec.c?h=v7.0#n2860)). Если сбой держится и после начала воспроизведения, значит неверно читается само presence detect пина. У ALC256 оно завязано на coef-регистры, которые `alc256_shutup` и `alc256_init` меняют при каждом засыпании и пробуждении: coef `0x46` (3k pull-low) и `0x57` ([alc269.c:454-550](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/sound/hda/codecs/realtek/alc269.c?h=v7.0#n454)). Обе ветки начинаются со сна кодека.
- У этой модели нет квирков. В таблице ALC269 для Xiaomi есть только `1d72:1602/1701/1901/1945/1947` ([alc269.c:7749-7753](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/sound/hda/codecs/realtek/alc269.c?h=v7.0#n7749)), а `1d72:2019` там нет. В `power_save_denylist` её тоже нет ([intel.c:2265-2300](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/sound/hda/controllers/intel.c?h=v7.0#n2265)). Похожие RedmiBook чинились квирком на mic-пин и coef jack detect, например `ALC255_FIXUP_XIAOMI_HEADSET_MIC` пишет coef `0x45=0x5089` ([alc269.c:5904-5913](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/sound/hda/codecs/realtek/alc269.c?h=v7.0#n5904); патч https://lore.kernel.org/all/20220713094133.9894-1-tangmeng@uniontech.com/T/).

## Как проверить при следующем сбое (только чтение)

Сразу, не переподключая наушники:

```bash
amixer -c 1 cget iface=CARD,name='Headphone Jack'
cat /sys/bus/hdaudio/devices/hdaudioC1D0/power/runtime_status
```

- `Headphone Jack` = `off` и кодек `suspended`: событие потеряно во сне. Подтверждает ветку с PM.
- Затем запустить воспроизведение. Кодек проснётся и перечитает джек. Если `Headphone Jack` станет `on`, это была потеря события, и `jackpoll_ms` её закроет.
- Если `Headphone Jack` и при воспроизведении (кодек `active`) остаётся `off`, неверно presence detect самого кодека. Тогда нужен `hda-verb` из `alsa-tools`, который не установлен: `sudo hda-verb /dev/snd/hwC1D0 0x21 GET_PIN_SENSE 0` (бит 31 — presence). И нужен квирк или coef, см. «Вариант C».

## Предложение (применяет пользователь)

**A. Разово при сбое — то же, что `alsamixer`:**

```bash
amixer -c 1 sset Headphone unmute
```

Риск: Speaker тоже играет, а громкость PipeWire крутит элемент `Speaker`, не `Headphone`. Переподключение штекера после пробуждения обычно чище, но проверить это при снятии было нельзя.

**B. Постоянно — опрос джека на карте 1 (рекомендую).** В `/etc/modprobe.d/alsa-base.conf` заменить строку 46:

```
options snd_hda_intel patch=,hda-alc256-jack.fw jackpoll_ms=,1000
```

Затем `sudo update-initramfs -u` и перезагрузка. Проверка: `cat /sys/module/snd_hda_intel/parameters/jackpoll_ms` должно начинаться с `0,1000`.

- Индекс 1 тот же, что у `patch=`: это контроллер `03:00.6`, и оба массива индексируются одним `dev` ([intel.c:1800-1801](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/sound/hda/controllers/intel.c?h=v7.0#n1800)). Допустимы значения 50–60000 мс.
- С ненулевым `jackpoll_interval` кодек не засыпает: `hda_codec_runtime_idle` возвращает `-EBUSY` ([codec.c:2923-2930](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/sound/hda/common/codec.c?h=v7.0#n2923)). Опрос сам читает джеки ([codec.c:636-649](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/sound/hda/common/codec.c?h=v7.0#n636)). Это закрывает обе ветки, если в D0 presence detect читается верно.
- Риск: кодек всё время в D0, батарея садится немного быстрее (замера нет). Если опрос мешает, возможны щелчки или нагрузка. Откат: убрать `jackpoll_ms=,1000`.

**B′. Альтернатива:** `options snd_hda_intel patch=,hda-alc256-jack.fw power_save=0`. Отключает автосон на всех HDA-картах, включая HDMI-карту 0, но опроса не добавляет. Unsolicited events будут приходить в бодрствующий кодек. Параметр описан как «Automatic power-saving timeout (in second, 0 = disable)» (https://docs.kernel.org/sound/alsa-configuration.html). Риск тот же — расход батареи.

**C. Если проверка покажет неверный presence detect в D0.** Нужно подобрать квирк. Например, временно `model=,alc256-asus-headset-mic` или coef Xiaomi в `[verb]` патча; это делается через `hdajackretask` из `alsa-tools`. Затем отправить квирк для `1d72:2019` в alsa-devel. Это отдельная работа, и без проверки делать её я не предлагаю.

Патч `hda-alc256-jack.fw` можно оставить: он безвреден. Но он не помогает, и его можно убрать, когда B подтвердится.

## Влияние на meetrec

**`them`.**
- Speaker и Headphones — порты **одного** узла `alsa_output.pci-0000_03_00.6.HiFi__hw_Generic_1__sink` (`device.profile.description = "Speaker + Headphones"`, `wpctl inspect @DEFAULT_AUDIO_SINK@`). Смена порта и сбой детекции не меняют default sink, поэтому `them` (`stream.capture.sink=true`) не перелинковывается и не теряет сэмплы.
- Monitor отдаёт сигнал до громкости и до ALSA-микшера. PipeWire docs: «Normally the monitor ports expose the raw unmodified signal on the input ports» (`monitor.channel-volumes`, https://docs.pipewire.org/page_man_pipewire-props_7.html). Выключенный `Headphone Playback Switch` — уже аппаратный микшер кодека. Поэтому `them.wav` пишет собеседников, даже когда пользователь их не слышит.

**`me`.**
- Default source — цифровой микрофон `alsa_input.…HiFi__hw_acp__source` на отдельной карте `acp`, джек на нём не сказывается. Микрофон гарнитуры (`[In] Mic2`, `availability group: Mic`) при сбое тоже `not available`, и `me` остаётся на встроенном.
- Перейдёт ли `me` на микрофон гарнитуры, когда детекция работает, не проверялось.

**События.**
- Когда детекция срабатывает, PipeWire меняет доступность портов, и `pactl subscribe` даёт `Event 'change' on card #…` и `… on sink #…`.
- При сбое событий нет, и обнаружить его по событиям нельзя. Тишина в записи его тоже не выдаст: `them` не молчит.
- Сбой мешает слушать, а не записывать.

**Минимальная проверка для демона.** Ловить надо не этот сбой, а настоящую тишину в записи: выключенный микрофон или пустой `them`. Раз в 30 с читать последние 10 с каждого WAV (`s16`, 16 кГц, это 320 000 байт с конца файла) и считать пик.

- `me`: если пик 0 дольше 60 с, `notify-send -u critical meetrec "me: микрофон пишет тишину"`.
- `them`: цифровые нули — норма, пока никто не говорит, поэтому предупреждать только в конце встречи, если пик всей дорожки 0.
- Для разбора в метаданные встречи стоит записывать `pactl -f json list sinks` → `active_port`, а также default sink и source на старте.
