import array
import logging
import subprocess
import time
from pathlib import Path
from types import MappingProxyType

from meetrec.audio import RATE, SAMPLE_BYTES
from meetrec.meeting import WAV_HEADER, repair_wav

log = logging.getLogger(__name__)

FORMAT = ("--rate", str(RATE), "--channels", "1", "--format", "s16")
# No --target / node.dont-reconnect: both tracks must follow the default device.
TRACKS = MappingProxyType({"me": "", "them": " stream.capture.sink=true"})
STOP_TIMEOUT_S = 10
MAX_GAP_S = 0.5


def pw_record(folder: Path, track: str, extra: str) -> subprocess.Popen[bytes]:
    props = f"{{ application.name=meetrec node.name=meetrec-{track} state.restore-target=false{extra} }}"
    return subprocess.Popen(["pw-record", *FORMAT, "-P", props, str(folder / f"{track}.wav")])


def stop_process(proc: subprocess.Popen[bytes]) -> None:
    try:
        proc.wait(timeout=STOP_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def recorded_s(path: Path) -> float:
    return (path.stat().st_size - WAV_HEADER) / SAMPLE_BYTES / RATE


class Recorder:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.started = time.monotonic()
        self.procs = {track: pw_record(folder, track, extra) for track, extra in TRACKS.items()}

    def stop(self) -> list[dict[str, object]]:
        for proc in self.procs.values():
            proc.terminate()
        for proc in self.procs.values():
            stop_process(proc)
        elapsed = time.monotonic() - self.started
        gaps = [self.gap(track, elapsed) for track in self.procs]
        return [gap for gap in gaps if gap]

    def gap(self, track: str, elapsed: float) -> dict[str, object] | None:
        path = self.folder / f"{track}.wav"
        if not path.exists():
            return None
        repair_wav(path)
        lost = elapsed - recorded_s(path)
        if lost <= MAX_GAP_S:
            return None
        log.warning("%s lost %.1f s of %s", self.folder.name, lost, track)
        return {"track": track, "lost_s": round(lost, 1)}

    def mic_silent(self, seconds: int) -> bool:
        path = self.folder / "me.wav"
        want = seconds * RATE * SAMPLE_BYTES
        if not path.exists() or path.stat().st_size - WAV_HEADER < want:
            return False
        with open(path, "rb") as wav_file:
            wav_file.seek(-want, 2)
            samples = array.array("h", wav_file.read(want))
        return not any(samples)
