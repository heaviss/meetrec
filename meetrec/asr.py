import logging
import subprocess
import sys
from pathlib import Path
from typing import Literal

import transcribe_cpp

from meetrec import transcript
from meetrec.audio import as_float_pcm, read_s16
from meetrec.config import Config

log = logging.getLogger(__name__)

Backend = Literal["vulkan", "cpu"]
BACKENDS: tuple[Backend, ...] = ("vulkan", "cpu")
CPU_THREADS = 4


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
    """Each attempt runs in its own process: a crash in ggml or Vulkan must not take the worker down."""
    for backend in BACKENDS:
        child = subprocess.run([sys.executable, "-m", "meetrec.process", "track", str(wav), str(tsv), backend])
        if child.returncode == 0:
            return
        log.warning("transcription of %s on %s failed", wav, backend)
    raise RuntimeError(f"transcription failed: {wav.name}")
