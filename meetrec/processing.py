import logging
import os
import signal
import subprocess
import sys
from collections import deque
from datetime import timedelta
from pathlib import Path

from meetrec.meeting import Meeting, list_meetings, now_iso, repair_wav
from meetrec.notify import notify
from meetrec.record import recorded_s

log = logging.getLogger(__name__)

NICE = ("nice", "-n", "19")


def recovered_stop(meeting: Meeting) -> str:
    """When the daemon died mid-meeting, the meeting ended where its recording ends."""
    me_wav = meeting.path / "me.wav"
    if not me_wav.exists():
        return now_iso()
    stopped = meeting.started_at + timedelta(seconds=recorded_s(me_wav))
    return stopped.isoformat(timespec="seconds")


def recover(meeting: Meeting) -> None:
    """Bring a meeting the daemon lost track of (crash, restart) back to the queue."""
    if meeting.status in {"recording", "pause"}:
        for wav in meeting.path.glob("*.wav"):
            repair_wav(wav)
        meeting.update(status="queued", stopped_at=meeting.meta["stopped_at"] or recovered_stop(meeting))
    elif meeting.status == "processing":
        meeting.update(status="queued")


def outcome(meeting: Meeting) -> str:
    folder = meeting.path
    if meeting.status == "error":
        error = meeting.meta["error"]
        return f"Ошибка обработки {folder.name}: {error}"
    if meeting.meta["summary_done"]:
        return f"Саммари готово: {folder}/summary.md"
    return f"Транскрипт готов, саммари не сделано: {folder}/transcript.md"


class Processing:
    """FIFO of closed meetings and the one worker process that handles them."""

    def __init__(self) -> None:
        self.pending: deque[Path] = deque()
        self.worker: subprocess.Popen[bytes] | None = None
        self.current: Path | None = None

    def enqueue(self, path: Path) -> None:
        if path not in self.pending:
            self.pending.append(path)

    def scan(self, recordings_dir: Path, recording: Path | None) -> None:
        for meeting in list_meetings(recordings_dir):
            if meeting.path in {recording, self.current}:
                continue
            recover(meeting)
            if meeting.status == "queued":
                self.enqueue(meeting.path)

    def pump(self, may_start: bool) -> None:
        if self.worker and self.worker.poll() is None:
            return
        if self.worker:
            self.finish(self.worker.returncode)
        if may_start and self.pending:
            self.start(self.pending.popleft())

    def start(self, path: Path) -> None:
        log.info("processing %s", path)
        self.current = path
        command = [*NICE, sys.executable, "-m", "meetrec.process", "meeting", str(path)]
        # Own process group, so suspend() stops the transcription children too.
        self.worker = subprocess.Popen(command, start_new_session=True)

    def signal_worker(self, signum: signal.Signals) -> None:
        if self.worker and self.worker.poll() is None:
            os.killpg(self.worker.pid, signum)

    def suspend(self) -> None:
        """A call started: keep the iGPU and CPU for it until the meeting is over."""
        self.signal_worker(signal.SIGSTOP)

    def resume(self) -> None:
        self.signal_worker(signal.SIGCONT)

    def finish(self, returncode: int) -> None:
        meeting = Meeting.load(self.current) if self.current else None
        self.worker = None
        self.current = None
        if meeting is None:
            return
        if meeting.status == "processing":
            meeting.update(status="error", error=f"worker exited with {returncode}")
        notify(outcome(meeting))
