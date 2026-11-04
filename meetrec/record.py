import array
import logging
import subprocess
import time
from pathlib import Path

from meetrec.meeting import WAV_HEADER, repair_wav

log = logging.getLogger(__name__)

RATE = 16000
FORMAT = ["--rate", str(RATE), "--channels", "1", "--format", "s16"]
# No --target / node.dont-reconnect: both tracks must follow the default device.
TRACKS = {"me": "", "them": " stream.capture.sink=true"}


class Recorder:
    def __init__(self, folder: Path):
        self.folder = folder
        self.started = time.monotonic()
        self.procs = {
            name: subprocess.Popen(
                [
                    "pw-record",
                    *FORMAT,
                    "-P",
                    f"{{ application.name=meetrec node.name=meetrec-{name} state.restore-target=false{extra} }}",
                    str(folder / f"{name}.wav"),
                ]
            )
            for name, extra in TRACKS.items()
        }

    def stop(self) -> list[dict]:
        for proc in self.procs.values():
            proc.terminate()
        for proc in self.procs.values():
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        elapsed = time.monotonic() - self.started
        gaps = []
        for name in self.procs:
            path = self.folder / f"{name}.wav"
            if not path.exists():
                continue
            repair_wav(path)
            lost = elapsed - (path.stat().st_size - WAV_HEADER) / 2 / RATE
            if lost > 0.5:
                log.warning("%s lost %.1f s of %s", self.folder.name, lost, name)
                gaps.append({"track": name, "lost_s": round(lost, 1)})
        return gaps

    def mic_silent(self, seconds: int = 10) -> bool:
        path = self.folder / "me.wav"
        want = seconds * RATE * 2
        if not path.exists() or path.stat().st_size - WAV_HEADER < want:
            return False
        with open(path, "rb") as f:
            f.seek(-want, 2)
            samples = array.array("h", f.read(want))
        return not any(samples)
