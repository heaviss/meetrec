"""Worker: python -m meetrec.process meeting <folder>"""

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from meetrec import transcript
from meetrec.audio import recorded_s
from meetrec.config import Config, load_config
from meetrec.echo import played_on_speakers
from meetrec.engines import Engines, Summarize, Transcribe
from meetrec.meeting import TRACKS, Meeting

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


def me_track(meeting: Meeting, cfg: Config, engines: Engines) -> Path:
    """A failed echo cancellation falls back to the raw track."""
    raw = meeting.wav("me")
    if not (cfg.echo_cancel and played_on_speakers(meeting)):
        return raw
    try:
        engines.clean_me(raw, meeting.wav("them"), meeting.clean_me)
    except RuntimeError as error:
        log.warning("LocalVQE failed: %s, transcribing the raw me.wav", error)
        meeting.append("warnings", f"LocalVQE failed: {error}")
        return raw
    return meeting.clean_me


def transcribe_or_skip(meeting: Meeting, wav: Path, tsv: Path, transcribe: Transcribe) -> None:
    """A track that pw-record never filled has no speech: the other track still gets transcribed."""
    if not wav.exists() or recorded_s(wav) <= 0:
        meeting.append("warnings", f"{wav.name} is empty, transcribed as silence")
        tsv.write_text("")
        return
    transcribe(wav, tsv, meeting.meta["language"])


def write_transcript(meeting: Meeting) -> None:
    tracks = [transcript.phrases(transcript.read_tokens(meeting.tokens(name)), name) for name in TRACKS]
    meeting.transcript.write_text(transcript.render(meeting.started_at, meeting.duration_s, *tracks))
    meeting.transcript_written()


def write_summary(meeting: Meeting, summarize: Summarize) -> None:
    try:
        summary = summarize(meeting.transcript.read_text(), meeting.meta["language"])
    except OSError, subprocess.SubprocessError, RuntimeError:
        log.exception("summary failed for %s", meeting.path)
        return
    if summary is None:
        log.info("no claude in PATH, skipping the summary of %s", meeting.path)
        meeting.summary_skipped()
        return
    meeting.summary.write_text(summary)
    meeting.summary_written()


def run_stages(meeting: Meeting, cfg: Config, engines: Engines) -> None:
    have_tokens = all(meeting.tokens(name).exists() for name in TRACKS)
    steps = plan(meeting.redo, have_tokens, meeting.transcript.exists(), meeting.summary_done)
    if steps.transcribe:
        meeting.enter("transcribe")
        transcribe_or_skip(meeting, me_track(meeting, cfg, engines), meeting.tokens("me"), engines.transcribe)
        transcribe_or_skip(meeting, meeting.wav("them"), meeting.tokens("them"), engines.transcribe)
    if steps.transcript:
        write_transcript(meeting)
    if steps.summary:
        meeting.enter("summary")
        write_summary(meeting, engines.summarize)


def process(meeting: Meeting, cfg: Config, engines: Engines) -> None:
    meeting.begin(cfg.language)
    try:
        run_stages(meeting, cfg, engines)
    except Exception as error:
        meeting.fail(f"{type(error).__name__}: {error}")
        raise
    meeting.finish()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    match sys.argv[1:]:
        case ["meeting", folder]:
            process(Meeting.load(Path(folder)), cfg, Engines.production(cfg))
        case _:
            sys.exit(__doc__)


if __name__ == "__main__":
    main()
