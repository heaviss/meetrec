"""Worker: python -m meetrec.process meeting <folder> | track <wav> <tsv> <backend>"""

import array
import ctypes
import logging
import subprocess
import sys
import wave
from pathlib import Path

from meetrec import config, transcript
from meetrec.config import Config
from meetrec.meeting import Meeting
from meetrec.summary import summarize

log = logging.getLogger(__name__)
SPEAKER_PORT_SUFFIX = "Speaker"


def read_s16(path: Path) -> array.array:
    with wave.open(str(path)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2), path
        return array.array("h", w.readframes(w.getnframes()))


def write_s16(path: Path, samples: array.array) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(samples.tobytes())


def cancel_echo(folder: Path, cfg: Config) -> Path:
    me, them = read_s16(folder / "me.wav"), read_s16(folder / "them.wav")
    n = min(len(me), len(them))
    me, them = me[:n], them[:n]
    # The build bakes its own directory into RUNPATH; load the deps by path so a moved build still works.
    for dep in ("libggml-base.so.0", "libggml.so.0"):
        ctypes.CDLL(str(cfg.localvqe_lib.parent / dep), mode=ctypes.RTLD_GLOBAL)
    lib = ctypes.CDLL(str(cfg.localvqe_lib))
    lib.localvqe_new.restype = ctypes.c_void_p
    lib.localvqe_last_error.restype = ctypes.c_char_p
    ctx = ctypes.c_void_p(lib.localvqe_new(str(cfg.localvqe_model).encode()))
    if not ctx.value:
        raise RuntimeError("localvqe_new failed")
    out = array.array("h", bytes(2 * n))
    buf = lambda a: (ctypes.c_int16 * n).from_buffer(a)  # noqa: E731
    try:
        if lib.localvqe_process_s16(ctx, buf(me), buf(them), n, buf(out)) != 0:
            raise RuntimeError(lib.localvqe_last_error(ctx).decode())
    finally:
        lib.localvqe_free(ctx)
    write_s16(folder / "me.clean.wav", out)
    return folder / "me.clean.wav"


def me_track(meeting: Meeting, cfg: Config) -> Path:
    if not any(p["port"] and p["port"].endswith(SPEAKER_PORT_SUFFIX) for p in meeting.meta["ports"]):
        return meeting.path / "me.wav"
    try:
        return cancel_echo(meeting.path, cfg)
    except Exception as e:
        log.exception("LocalVQE failed, transcribing the raw me.wav")
        meeting.update(warnings=[*meeting.meta["warnings"], f"LocalVQE failed: {e}"])
        return meeting.path / "me.wav"


def transcribe_track(wav: Path, tsv: Path, backend: str, cfg: Config) -> None:
    import transcribe_cpp as tc  # noqa: PLC0415 heavy native lib, loaded only in the track child

    pcm = array.array("f", (x / 32768 for x in read_s16(wav)))
    model = tc.Model(str(cfg.gigaam_model), backend=backend)
    session = model.session(n_threads=4) if backend == "cpu" else model.session()
    result = session.run(pcm, language="ru", timestamps="token")
    transcript.write_tokens(tsv, [(t.t0_ms, t.t1_ms, t.text) for t in result.tokens])


def transcribe(wav: Path, tsv: Path) -> None:
    for backend in ("vulkan", "cpu"):
        if (
            subprocess.run([sys.executable, "-m", "meetrec.process", "track", str(wav), str(tsv), backend]).returncode
            == 0
        ):
            return
        log.warning("transcription of %s on %s failed", wav, backend)
    raise RuntimeError(f"transcription failed: {wav.name}")


def process(folder: Path, cfg: Config) -> None:
    meeting = Meeting.load(folder)
    redo = meeting.meta.get("redo") or "missing"
    meeting.update(status="processing", redo=None, error=None)
    try:
        tokens = {name: folder / f"{name}.tokens.tsv" for name in ("me", "them")}
        rebuild = redo == "all" or not all(p.exists() for p in tokens.values())
        if rebuild:
            transcribe(me_track(meeting, cfg), tokens["me"])
            transcribe(folder / "them.wav", tokens["them"])
        if rebuild or redo == "transcript" or not (folder / "transcript.md").exists():
            text = transcript.render(
                meeting.started_at,
                meeting.duration_s,
                *(transcript.phrases(transcript.read_tokens(p), name) for name, p in tokens.items()),
            )
            (folder / "transcript.md").write_text(text)
            meeting.update(summary_done=False)
        if not meeting.meta["summary_done"]:
            try:
                (folder / "summary.md").write_text(summarize((folder / "transcript.md").read_text(), cfg))
                meeting.update(summary_done=True)
            except Exception:
                log.exception("summary failed for %s", folder)
        meeting.update(status="done")
    except Exception as e:
        meeting.update(status="error", error=f"{type(e).__name__}: {e}")
        raise


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = config.load()
    match sys.argv[1:]:
        case ["meeting", folder]:
            process(Path(folder), cfg)
        case ["track", wav, tsv, backend]:
            transcribe_track(Path(wav), Path(tsv), backend, cfg)
        case _:
            sys.exit(__doc__)


if __name__ == "__main__":
    main()
