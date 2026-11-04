# CLAUDE.md

meetrec: a Linux daemon that notices a call, records `me`/`them` tracks, transcribes them locally (GigaAM for Russian, Parakeet for English) and summarizes with `claude -p`. Users read [README.md](README.md); what to build and why lives in [SPEC.md](wayfinder/SPEC.md), the words in [GLOSSARY.md](GLOSSARY.md).

## Where decisions live

- [SPEC.md](wayfinder/SPEC.md) is the single source of truth for behaviour. Change the spec in the same commit as the behaviour.
- `wayfinder/` holds the first map and its tickets: the reasoning, measurements and research behind each spec section (SPEC links them as `→ 08`). Read the ticket before reversing a decision; an open ticket is a question still to settle.
- New domain terms go into GLOSSARY.md as they settle.

## Checks

All four pass before a commit:

```bash
uv run pytest -q
uv run mypy meetrec tests
uv run flake8 meetrec tests          # wemake-python-styleguide; thresholds in setup.cfg
uvx ruff check meetrec tests && uvx ruff format --check meetrec tests
```

Fix wemake findings in the code. Raise a threshold in `setup.cfg` only with a comment saying why.

## Gotchas

- Live runs of the daemon or the worker (`python -m meetrec.process`) send real `notify-send` notifications and call `claude`; pytest does neither. Point live runs at a scratch `recordings_dir` and `data_dir` through `Config(...)`, never at `~/Recordings`.
- Tests use synthetic tokens and audio. Real meeting audio and transcripts stay out of the repo: they are other people's speech.
- Python 3.14: `except A, B:` without parentheses is valid syntax here (PEP 758), ruff formats it that way.
- `systemctl --user kill` signals the whole cgroup by default; signal the daemon only with `--kill-whom=main`, or `pw-record` dies mid-meeting.
- The LocalVQE build bakes its build dir into RUNPATH, so `echo.py` loads `libggml*.so.0` by path.

## Install from a clone

`uv tool install --editable . --python 3.14`, then `meetrec setup`. A code change takes effect after `systemctl --user restart meetrec`.

## Agent skills

### Issue tracker

Local markdown in the repo: wayfinder maps in `wayfinder/` and `.scratch/<effort>/`, issues in `.scratch/<feature>/issues/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default roles, written as `status:` in an issue's frontmatter. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the root. See `docs/agents/domain.md`.
