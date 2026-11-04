"""Worker: python -m meetrec.process

meeting <folder> | track <wav> <tsv> <backend> <language> | echo <mic> <ref> <out>
"""

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from meetrec import transcript
from meetrec.asr import parse_backend, require_model, transcribe, transcribe_track
from meetrec.audio import recorded_s
from meetrec.config import Config, load_config
from meetrec.echo import cancel_echo, played_on_speakers
from meetrec.meeting import TRACKS, Meeting
from meetrec.summary import claude_available, summarize

log = logging.getLogger(__name__)


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
    raw = meeting.wav("me")
    if not (cfg.echo_cancel and played_on_speakers(meeting)):
        return raw
    paths = (raw, meeting.wav("them"), meeting.clean_me)
    child = subprocess.run([sys.executable, "-m", "meetrec.process", "echo", *map(str, paths)])
    if child.returncode == 0:
        return meeting.clean_me
    log.warning("LocalVQE failed with %s, transcribing the raw me.wav", child.returncode)
    meeting.append("warnings", f"LocalVQE failed with exit code {child.returncode}")
    return raw


def transcribe_or_skip(meeting: Meeting, wav: Path, tsv: Path, language: str) -> None:
    """A track that pw-record never filled has no speech: the other track still gets transcribed."""
    if not wav.exists() or recorded_s(wav) <= 0:
        meeting.append("warnings", f"{wav.name} is empty, transcribed as silence")
        tsv.write_text("")
        return
    transcribe(wav, tsv, language)


def write_transcript(meeting: Meeting) -> None:
    tracks = [transcript.phrases(transcript.read_tokens(meeting.tokens(name)), name) for name in TRACKS]
    meeting.transcript.write_text(transcript.render(meeting.started_at, meeting.duration_s, *tracks))
    meeting.transcript_written()


def write_summary(meeting: Meeting, cfg: Config) -> None:
    if not claude_available():
        log.info("no claude in PATH, skipping the summary of %s", meeting.path)
        meeting.summary_skipped()
        return
    try:
        summary = summarize(meeting.transcript.read_text(), cfg, meeting.meta["language"])
    except OSError, subprocess.SubprocessError, RuntimeError:
        log.exception("summary failed for %s", meeting.path)
        return
    meeting.summary.write_text(summary)
    meeting.summary_written()


def run_stages(meeting: Meeting, cfg: Config) -> None:
    have_tokens = all(meeting.tokens(name).exists() for name in TRACKS)
    steps = plan(meeting.redo, have_tokens, meeting.transcript.exists(), meeting.summary_done)
    if steps.transcribe:
        language = meeting.meta["language"]
        require_model(cfg, language)
        meeting.enter("transcribe")
        transcribe_or_skip(meeting, me_track(meeting, cfg), meeting.tokens("me"), language)
        transcribe_or_skip(meeting, meeting.wav("them"), meeting.tokens("them"), language)
    if steps.transcript:
        write_transcript(meeting)
    if steps.summary:
        meeting.enter("summary")
        write_summary(meeting, cfg)


def process(folder: Path, cfg: Config) -> None:
    meeting = Meeting.load(folder)
    meeting.begin(cfg.language)
    try:
        run_stages(meeting, cfg)
    except Exception as error:
        meeting.fail(f"{type(error).__name__}: {error}")
        raise
    meeting.finish()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    match sys.argv[1:]:
        case ["meeting", folder]:
            process(Path(folder), cfg)
        case ["track", wav, tsv, backend, language]:
            transcribe_track(Path(wav), Path(tsv), parse_backend(backend), cfg.asr_model(language), language)
        case ["echo", mic, ref, out]:
            cancel_echo(Path(mic), Path(ref), Path(out), cfg)
        case _:
            sys.exit(__doc__)


if __name__ == "__main__":
    main()
