# meetrec

A Linux daemon that records your calls by itself and transcribes them on your machine.

A call starts when a browser or Zoom takes the microphone. The daemon records two tracks: `me` is your microphone, `them` is everything the computer plays. When the call is over, a local speech model transcribes both tracks, and a summarizer (`claude -p` by default, any command you configure) writes a summary with decisions and tasks.

How it works and why: [SPEC.md](wayfinder/SPEC.md) (in Russian), terms in [GLOSSARY.md](GLOSSARY.md).

## Privacy

Audio never leaves your machine: recording and transcription are local. The transcript text goes to the summarizer: by default your own `claude` CLI, which sends it to Anthropic. Point `summary_command` at a local model to keep the text on your machine too. Without the summarizer in `PATH`, meetrec skips the summary and keeps only the local transcript.

## Languages

One language per meeting, set by `language` in the config:

- `ru` (default): [GigaAM-v3](https://github.com/salute-developers/GigaAM);
- `en`: [Parakeet TDT 0.6B v2](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2).

Meetings that mix languages are not supported, and the language is not detected automatically. The summary is written in the meeting's language.

## Requirements

- Linux with PipeWire: `pactl`, `pw-record`, `notify-send`;
- [`uv`](https://docs.astral.sh/uv/);
- [`claude`](https://docs.anthropic.com/en/docs/claude-code), logged in, for summaries (optional; or any other summarizer, see [Configure](#configure)).

For echo cancellation (`echo_cancel = true`) also `git` and `g++`: `meetrec setup` builds [LocalVQE](https://github.com/localai-org/LocalVQE).

## Install and update

```bash
uv tool install git+https://github.com/heaviss/meetrec --python 3.14
meetrec setup
```

`meetrec setup` downloads the model for your language into `~/.local/share/meetrec/models/`, builds LocalVQE if `echo_cancel = true`, and enables a `systemd --user` service. It is safe to rerun: finished steps are skipped. Rerun it after changing `language` or turning on `echo_cancel`.

Update:

```bash
uv tool upgrade meetrec
meetrec setup
systemctl --user restart meetrec
```

## Usage

There is nothing to do: the daemon notices a call and sends notifications when recording starts, when the meeting is recorded and when the summary is ready.

Each meeting gets its own folder `~/Recordings/<YYYY-MM-DD-HHMM>/`:

| file | contents |
|---|---|
| `summary.md` | summary, decisions, tasks, open questions |
| `transcript.md` | `me` and `them` lines with timestamps |
| `me.wav`, `them.wav` | audio, 16 kHz mono |
| `me.clean.wav` | `me` without echo; only with `echo_cancel = true` when sound went to the speakers |
| `me.tokens.tsv`, `them.tokens.tsv` | words with timestamps; the transcript is built from them |
| `meta.json` | status, language, apps, output devices, errors |

Meetings shorter than 2 minutes are deleted automatically.

```bash
meetrec status                                    # what the daemon does, the queue, meetings with an error or no summary
meetrec redo ~/Recordings/<folder>                # finish what is missing: transcription or summary
meetrec redo ~/Recordings/<folder> --transcript   # rebuild transcript.md and the summary without transcribing
meetrec redo ~/Recordings/<folder> --all          # everything again
meetrec redo ~/Recordings/<folder> --language en  # the meeting was in English: everything again with the English model
journalctl --user -u meetrec -f                   # daemon log
```

### Configure

The config is optional. Put your own values into `~/.config/meetrec/config.toml`; all keys and defaults are in [SPEC.md](wayfinder/SPEC.md#3-конфиг).

```toml
language = "en"                   # ru or en
pause_s = 60                      # how long to wait for the microphone to come back before closing the meeting
echo_cancel = true                # remove echo from me when the call went through the speakers
user_name = "Jane Doe"            # who `me` is in the summary; defaults to your full name from passwd
glossary_repo = "~/src/work-repo" # a git repo whose GLOSSARY*.md files help the summary spell your terms
```

`glossary_repo` adds every `GLOSSARY-MAP.md` and `*GLOSSARY.md` tracked in that repo to the summary input. Without it the summary has no glossary.

`summary_command` replaces `claude` with any command that reads the meeting on stdin and prints the summary to stdout. `{prompt_file}` in its arguments becomes the path to the system prompt; without it the prompt is put ahead of the transcript on stdin. `[]` turns summaries off.

```toml
summary_command = ["ollama", "run", "qwen3:14b"]
summary_timeout_s = 3600          # local models are slower; the default is 900
```

A local summarizer is not paused when a new call starts, so it shares the GPU and CPU with the call.

After editing: `systemctl --user restart meetrec`.

## Clean up recordings

Each meeting is a folder with the date in its name; delete it whole. The commands below touch only such folders. Leave alone a meeting that is being recorded or processed: `meetrec status` shows it.

To drop audio older than 30 days from meetings that are already transcribed and keep the text, add to the config:

```toml
audio_retention_days = 30         # the default 0 keeps audio forever
```

The daemon checks on start and after each processed meeting. Audio of a meeting with an error or still in the queue stays. After this, `meetrec redo --transcript` still works for the meeting, `redo --all` refuses: there is nothing left to transcribe.

Delete meetings older than 90 days:

```bash
find ~/Recordings -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +90 -exec rm -r {} +
```

## Uninstall

```bash
systemctl --user disable --now meetrec
rm ~/.config/systemd/user/meetrec.service
systemctl --user daemon-reload
uv tool uninstall meetrec
rm -rf ~/.local/share/meetrec ~/.config/meetrec
```

Recordings in `~/Recordings` stay; delete them yourself if you don't need them.

## Limitations

- Browsers keep the microphone while you are muted and on the preview screen, so a meeting closes only after the microphone has been free for `pause_s` (30 s by default).
- The Zoom desktop app has not been tried; browser calls have.
- On some laptops the headphone jack is not detected and PipeWire reports the speakers, so meetrec cannot tell headphones from speakers. That is why `echo_cancel` is off by default.

On macOS or Windows, look at [amanu](https://github.com/gsamat/amanu).

## Third-party components

meetrec bundles none of these; `uv` and `meetrec setup` download them, and models download under their own licenses:

- [transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) and ggml: MIT;
- [GigaAM-v3](https://huggingface.co/ai-sage/GigaAM-v3) and its [GGUF conversion](https://huggingface.co/handy-computer/gigaam-v3-e2e-ctc-gguf): MIT;
- [Parakeet TDT 0.6B v2](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2) by NVIDIA, [GGUF](https://huggingface.co/handy-computer/parakeet-tdt-0.6b-v2-gguf): CC BY 4.0;
- [LocalVQE](https://github.com/localai-org/LocalVQE) code and [model](https://huggingface.co/LocalAI-io/LocalVQE): Apache-2.0.

Summaries are written by the `claude` CLI under Anthropic's terms.

## License

[MIT](LICENSE)
