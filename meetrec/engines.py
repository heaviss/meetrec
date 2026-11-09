"""The heavy engines of processing, and their child processes: python -m meetrec.engines

track <wav> <tsv> <backend> <language> | echo <mic> <ref> <out>
"""

import logging
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from meetrec.asr import BACKENDS, parse_backend, require_model, transcribe_track
from meetrec.config import Config, load_config
from meetrec.echo import cancel_echo
from meetrec.summary import summarize, summarizer_available

log = logging.getLogger(__name__)

Transcribe = Callable[[Path, Path, str], None]
CleanMe = Callable[[Path, Path, Path], None]
Summarize = Callable[[str, str], str | None]


@dataclass(frozen=True)
class Engines:
    """What processing runs on a meeting's audio and text.

    transcribe(wav, tsv, language) and clean_me(mic, ref, out) raise RuntimeError on failure;
    summarize(transcript, language) returns None when there is no summarizer at all.
    """

    transcribe: Transcribe
    clean_me: CleanMe
    summarize: Summarize

    @classmethod
    def production(cls, cfg: Config) -> Engines:
        return cls(
            transcribe=partial(transcribe_in_child, cfg),
            clean_me=clean_me_in_child,
            summarize=partial(summarize_if_available, cfg),
        )


def run_child(*args: str) -> int:
    return subprocess.run([sys.executable, "-m", "meetrec.engines", *args]).returncode


def transcribe_in_child(cfg: Config, wav: Path, tsv: Path, language: str) -> None:
    """Each attempt runs in its own process: a crash in ggml or Vulkan must not take the worker down."""
    require_model(cfg, language)
    for backend in BACKENDS:
        if run_child("track", str(wav), str(tsv), backend, language) == 0:
            return
        log.warning("transcription of %s on %s failed", wav, backend)
    raise RuntimeError(f"transcription failed: {wav.name}")


def clean_me_in_child(mic: Path, ref: Path, out: Path) -> None:
    """LocalVQE runs in a child too: a native crash there fails this call, not the worker."""
    returncode = run_child("echo", str(mic), str(ref), str(out))
    if returncode:
        raise RuntimeError(f"exit code {returncode}")


def summarize_if_available(cfg: Config, transcript: str, language: str) -> str | None:
    if not summarizer_available(cfg.summary_command):
        return None
    return summarize(transcript, cfg, language)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    match sys.argv[1:]:
        case ["track", wav, tsv, backend, language]:
            transcribe_track(Path(wav), Path(tsv), parse_backend(backend), cfg.asr_model(language), language)
        case ["echo", mic, ref, out]:
            cancel_echo(Path(mic), Path(ref), Path(out), cfg)
        case _:
            sys.exit(__doc__)


if __name__ == "__main__":
    main()
