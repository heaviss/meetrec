import array
import logging
import subprocess
import time
from pathlib import Path
from types import MappingProxyType

from meetrec.audio import RATE, SAMPLE_BYTES, WAV_HEADER, recorded_s, repair_wav
from meetrec.meeting import Meeting, now_iso

log = logging.getLogger(__name__)

FORMAT = ("--rate", str(RATE), "--channels", "1", "--format", "s16")
# No --target / node.dont-reconnect: both tracks must follow the default device.
TRACK_PROPS = MappingProxyType({"me": "", "them": " stream.capture.sink=true"})
STOP_TIMEOUT_S = 10
MAX_GAP_S = 0.5


def pw_record(wav: Path, track: str, extra: str) -> subprocess.Popen[bytes]:
    props = f"{{ application.name=meetrec node.name=meetrec-{track} state.restore-target=false{extra} }}"
    return subprocess.Popen(["pw-record", *FORMAT, "-P", props, str(wav)])


def stop_process(proc: subprocess.Popen[bytes]) -> None:
    try:
        proc.wait(timeout=STOP_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


class Recorder:
    def __init__(self, meeting: Meeting) -> None:
        self.meeting = meeting
        self.started = time.monotonic()
        self.procs = {track: pw_record(meeting.wav(track), track, extra) for track, extra in TRACK_PROPS.items()}

    def stop(self) -> list[dict[str, object]]:
        for proc in self.procs.values():
            proc.terminate()
        for proc in self.procs.values():
            stop_process(proc)
        elapsed = time.monotonic() - self.started
        gaps = [self.gap(track, elapsed) for track in self.procs]
        return [gap for gap in gaps if gap]

    def gap(self, track: str, elapsed: float) -> dict[str, object] | None:
        path = self.meeting.wav(track)
        if not path.exists():
            return None
        repair_wav(path)
        lost = elapsed - recorded_s(path)
        if lost <= MAX_GAP_S:
            return None
        log.warning("%s lost %.1f s of %s", self.meeting.path.name, lost, track)
        return {"track": track, "at": now_iso(), "lost_s": round(lost, 1)}

    def dead_tracks(self) -> set[str]:
        return {track for track, proc in self.procs.items() if proc.poll() is not None}

    def mic_silent(self, seconds: int) -> bool:
        path = self.meeting.wav("me")
        want = seconds * RATE * SAMPLE_BYTES
        if not path.exists() or path.stat().st_size - WAV_HEADER < want:
            return False
        with open(path, "rb") as wav_file:
            wav_file.seek(-want, 2)
            samples = array.array("h", wav_file.read(want))
        return not any(samples)
