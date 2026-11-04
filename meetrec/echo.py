import array
import ctypes
from pathlib import Path

from meetrec.audio import read_s16, write_s16
from meetrec.config import Config
from meetrec.meeting import Meeting

SPEAKER_PORT_SUFFIX = "Speaker"
# The build bakes its own directory into RUNPATH; load the deps by path so a moved build still works.
GGML_DEPS = ("libggml-base.so.0", "libggml.so.0")


def load_localvqe(lib_path: Path) -> ctypes.CDLL:
    for dep in GGML_DEPS:
        ctypes.CDLL(str(lib_path.parent / dep), mode=ctypes.RTLD_GLOBAL)
    lib = ctypes.CDLL(str(lib_path))
    lib.localvqe_new.restype = ctypes.c_void_p
    lib.localvqe_last_error.restype = ctypes.c_char_p
    return lib


def as_c_int16(samples: array.array[int]) -> ctypes.Array[ctypes.c_int16]:
    return (ctypes.c_int16 * len(samples)).from_buffer(samples)


def run_localvqe(lib: ctypes.CDLL, model: Path, mic: array.array[int], ref: array.array[int]) -> array.array[int]:
    ctx = ctypes.c_void_p(lib.localvqe_new(str(model).encode()))
    if not ctx.value:
        raise RuntimeError("localvqe_new failed")
    cleaned = array.array("h", bytes(len(mic) * 2))
    status = lib.localvqe_process_s16(ctx, as_c_int16(mic), as_c_int16(ref), len(mic), as_c_int16(cleaned))
    error = lib.localvqe_last_error(ctx) if status else b""
    lib.localvqe_free(ctx)
    if status:
        raise RuntimeError(error.decode())
    return cleaned


def cancel_echo(mic_wav: Path, ref_wav: Path, out: Path, cfg: Config) -> None:
    mic = read_s16(mic_wav)
    ref = read_s16(ref_wav)
    length = min(len(mic), len(ref))
    cleaned = run_localvqe(load_localvqe(cfg.localvqe_lib), cfg.localvqe_model, mic[:length], ref[:length])
    write_s16(out, cleaned)


def played_on_speakers(meeting: Meeting) -> bool:
    return any(str(entry["port"] or "").endswith(SPEAKER_PORT_SUFFIX) for entry in meeting.meta["ports"])
