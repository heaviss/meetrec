import array
from pathlib import Path
from typing import Any, Literal

import transcribe_cpp

from meetrec import transcript
from meetrec.audio import RATE, as_float_pcm, read_s16
from meetrec.config import Config

Backend = Literal["vulkan", "cpu"]
BACKENDS: tuple[Backend, ...] = ("vulkan", "cpu")
CPU_THREADS = 4
# Parakeet's memory grows with the input, ~1.4 GiB per 5 min on CPU, and an hour fails outright.
CHUNK_S = 300
CHUNK_SAMPLES = CHUNK_S * RATE
SEARCH_SAMPLES = 10 * RATE
FRAME_SAMPLES = RATE // 10


def parse_backend(name: str) -> Backend:
    for backend in BACKENDS:
        if backend == name:
            return backend
    raise ValueError(f"unknown backend {name}")


def require_model(cfg: Config, language: str) -> None:
    model = cfg.asr_model(language)
    if not model.exists():
        raise RuntimeError(f'{model.name} is missing: set language = "{language}" in the config and run meetrec setup')


def frame_peak(samples: array.array[int], start: int) -> int:
    end = start + FRAME_SAMPLES
    return max(map(abs, samples[start:end]))


def quietest_frame(samples: array.array[int], start: int, stop: int) -> int:
    frames = range(start, stop - FRAME_SAMPLES + 1, FRAME_SAMPLES)
    return min(frames, key=lambda at: frame_peak(samples, at))


def chunks(samples: array.array[int]) -> list[tuple[int, int]]:
    """Spans of at most CHUNK_S, each cut at the quietest 0.1 s of its last 10 s: a cut rarely splits a word."""
    bounds = [0]
    while len(samples) - bounds[-1] > CHUNK_SAMPLES:
        end = bounds[-1] + CHUNK_SAMPLES
        bounds.append(quietest_frame(samples, end - SEARCH_SAMPLES, end))
    return list(zip(bounds, [*bounds[1:], len(samples)], strict=True))


def recognize(session: Any, samples: array.array[int], span: tuple[int, int], language: str) -> list[transcript.Token]:
    start, end = span
    recognized = session.run(as_float_pcm(samples[start:end]), language=language, timestamps="token")
    offset_ms = start * transcript.MS_PER_S // RATE
    return [(token.t0_ms + offset_ms, token.t1_ms + offset_ms, token.text) for token in recognized.tokens]


def transcribe_track(wav: Path, tsv: Path, backend: Backend, model_path: Path, language: str) -> None:
    model = transcribe_cpp.Model(str(model_path), backend=backend)
    session = model.session(n_threads=CPU_THREADS) if backend == "cpu" else model.session()
    samples = read_s16(wav)
    spans = [(0, len(samples))] if model.supports("long_form") else chunks(samples)
    transcript.write_tokens(tsv, [token for span in spans for token in recognize(session, samples, span, language)])
