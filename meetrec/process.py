"""Worker: python -m meetrec.process meeting <folder> | track <wav> <tsv> <backend>"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Literal

import transcribe_cpp

from meetrec import transcript
from meetrec.audio import as_float_pcm, read_s16
from meetrec.config import Config, load_config
from meetrec.echo import me_track
from meetrec.meeting import Meeting
from meetrec.summary import summarize

log = logging.getLogger(__name__)

Backend = Literal["vulkan", "cpu"]
BACKENDS: tuple[Backend, ...] = ("vulkan", "cpu")
CPU_THREADS = 4
TRACKS = ("me", "them")


def parse_backend(name: str) -> Backend:
    for backend in BACKENDS:
        if backend == name:
            return backend
    raise ValueError(f"unknown backend {name}")


def transcribe_track(wav: Path, tsv: Path, backend: Backend, cfg: Config) -> None:
    model = transcribe_cpp.Model(str(cfg.gigaam_model), backend=backend)
    session = model.session(n_threads=CPU_THREADS) if backend == "cpu" else model.session()
    recognized = session.run(as_float_pcm(read_s16(wav)), language="ru", timestamps="token")
    transcript.write_tokens(tsv, [(token.t0_ms, token.t1_ms, token.text) for token in recognized.tokens])


def transcribe(wav: Path, tsv: Path) -> None:
    for backend in BACKENDS:
        child = subprocess.run([sys.executable, "-m", "meetrec.process", "track", str(wav), str(tsv), backend])
        if child.returncode == 0:
            return
        log.warning("transcription of %s on %s failed", wav, backend)
    raise RuntimeError(f"transcription failed: {wav.name}")


def ensure_tokens(meeting: Meeting, redo: str, cfg: Config) -> bool:
    tokens = [meeting.path / f"{track}.tokens.tsv" for track in TRACKS]
    if redo != "all" and all(path.exists() for path in tokens):
        return False
    transcribe(me_track(meeting, cfg), tokens[0])
    transcribe(meeting.path / "them.wav", tokens[1])
    return True


def ensure_transcript(meeting: Meeting, rebuild: bool) -> None:
    path = meeting.path / "transcript.md"
    if path.exists() and not rebuild:
        return
    tracks = [transcript.phrases(transcript.read_tokens(meeting.path / f"{name}.tokens.tsv"), name) for name in TRACKS]
    path.write_text(transcript.render(meeting.started_at, meeting.duration_s, *tracks))
    meeting.update(summary_done=False)


def ensure_summary(meeting: Meeting, cfg: Config) -> None:
    if meeting.meta["summary_done"]:
        return
    try:
        summary = summarize((meeting.path / "transcript.md").read_text(), cfg)
    except OSError, subprocess.SubprocessError, RuntimeError:
        log.exception("summary failed for %s", meeting.path)
        return
    (meeting.path / "summary.md").write_text(summary)
    meeting.update(summary_done=True)


def run_stages(meeting: Meeting, redo: str, cfg: Config) -> None:
    rebuilt = ensure_tokens(meeting, redo, cfg)
    ensure_transcript(meeting, rebuilt or redo == "transcript")
    ensure_summary(meeting, cfg)


def process(folder: Path, cfg: Config) -> None:
    meeting = Meeting.load(folder)
    redo = meeting.meta.get("redo") or "missing"
    meeting.update(status="processing", redo=None, error=None)
    try:
        run_stages(meeting, redo, cfg)
    except Exception as error:
        meeting.update(status="error", error=f"{type(error).__name__}: {error}")
        raise
    meeting.update(status="done")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    match sys.argv[1:]:
        case ["meeting", folder]:
            process(Path(folder), cfg)
        case ["track", wav, tsv, backend]:
            transcribe_track(Path(wav), Path(tsv), parse_backend(backend), cfg)
        case _:
            sys.exit(__doc__)


if __name__ == "__main__":
    main()
