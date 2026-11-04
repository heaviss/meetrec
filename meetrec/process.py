"""Worker: python -m meetrec.process meeting <folder> | track <wav> <tsv> <backend> <language> | echo <folder>"""

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from meetrec import transcript
from meetrec.asr import parse_backend, require_model, transcribe, transcribe_track
from meetrec.config import Config, load_config
from meetrec.echo import cancel_echo, played_on_speakers
from meetrec.meeting import Meeting
from meetrec.record import recorded_s
from meetrec.summary import claude_available, summarize

log = logging.getLogger(__name__)

TRACKS = ("me", "them")


@dataclass(frozen=True)
class Plan:
    transcribe: bool
    transcript: bool
    summary: bool


def plan(redo: str, have_tokens: bool, have_transcript: bool, summary_done: bool) -> Plan:
    """What to (re)do: `missing` fills the gaps, `transcript` rebuilds from tokens, `all` starts over."""
    must_transcribe = redo == "all" or not have_tokens
    must_render = must_transcribe or redo == "transcript" or not have_transcript
    return Plan(transcribe=must_transcribe, transcript=must_render, summary=must_render or not summary_done)


def me_track(meeting: Meeting, cfg: Config) -> Path:
    """LocalVQE runs in a child too: a native crash there falls back to the raw track."""
    if not (cfg.echo_cancel and played_on_speakers(meeting)):
        return meeting.path / "me.wav"
    child = subprocess.run([sys.executable, "-m", "meetrec.process", "echo", str(meeting.path)])
    if child.returncode == 0:
        return meeting.path / "me.clean.wav"
    log.warning("LocalVQE failed with %s, transcribing the raw me.wav", child.returncode)
    meeting.append("warnings", f"LocalVQE failed with exit code {child.returncode}")
    return meeting.path / "me.wav"


def transcribe_or_skip(meeting: Meeting, wav: Path, tsv: Path, language: str) -> None:
    """A track that pw-record never filled has no speech: the other track still gets transcribed."""
    if not wav.exists() or recorded_s(wav) <= 0:
        meeting.append("warnings", f"{wav.name} is empty, transcribed as silence")
        tsv.write_text("")
        return
    transcribe(wav, tsv, language)


def write_transcript(meeting: Meeting) -> None:
    tracks = [transcript.phrases(transcript.read_tokens(meeting.path / f"{name}.tokens.tsv"), name) for name in TRACKS]
    (meeting.path / "transcript.md").write_text(transcript.render(meeting.started_at, meeting.duration_s, *tracks))
    meeting.update(summary_done=False)


def write_summary(meeting: Meeting, cfg: Config) -> None:
    if not claude_available():
        log.info("no claude in PATH, skipping the summary of %s", meeting.path)
        meeting.update(summary_skipped=True)
        return
    try:
        summary = summarize((meeting.path / "transcript.md").read_text(), cfg, meeting.meta["language"])
    except OSError, subprocess.SubprocessError, RuntimeError:
        log.exception("summary failed for %s", meeting.path)
        return
    (meeting.path / "summary.md").write_text(summary)
    meeting.update(summary_done=True, summary_skipped=False)


def run_stages(meeting: Meeting, redo: str, cfg: Config) -> None:
    folder = meeting.path
    have_tokens = all((folder / f"{name}.tokens.tsv").exists() for name in TRACKS)
    steps = plan(redo, have_tokens, (folder / "transcript.md").exists(), meeting.meta["summary_done"])
    if steps.transcribe:
        language = meeting.meta["language"]
        require_model(cfg, language)
        meeting.update(stage="transcribe")
        transcribe_or_skip(meeting, me_track(meeting, cfg), folder / "me.tokens.tsv", language)
        transcribe_or_skip(meeting, folder / "them.wav", folder / "them.tokens.tsv", language)
    if steps.transcript:
        write_transcript(meeting)
    if steps.summary:
        meeting.update(stage="summary")
        write_summary(meeting, cfg)


def process(folder: Path, cfg: Config) -> None:
    meeting = Meeting.load(folder)
    redo = meeting.meta.get("redo") or "missing"
    # Meetings from before the language setting, and new ones, take the configured language once.
    meeting.update(status="processing", error=None, stage=None, language=meeting.meta.get("language") or cfg.language)
    try:
        run_stages(meeting, redo, cfg)
    except Exception as error:
        meeting.update(status="error", stage=None, error=f"{type(error).__name__}: {error}")
        raise
    # redo is cleared only now: a worker that dies mid-way retries the same stage.
    meeting.update(status="done", stage=None, redo=None)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    match sys.argv[1:]:
        case ["meeting", folder]:
            process(Path(folder), cfg)
        case ["track", wav, tsv, backend, language]:
            transcribe_track(Path(wav), Path(tsv), parse_backend(backend), cfg.asr_model(language), language)
        case ["echo", folder]:
            cancel_echo(Path(folder), cfg)
        case _:
            sys.exit(__doc__)


if __name__ == "__main__":
    main()
