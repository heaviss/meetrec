import logging
import os
import shutil
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
BASE_BUDGET_S = 1800
QUEUED = "queued"
UNFINISHED = frozenset((QUEUED, "processing"))


def recovered_stop(meeting: Meeting) -> str:
    """When the daemon died mid-meeting, the meeting ended where its recording ends."""
    me_wav = meeting.path / "me.wav"
    if not me_wav.exists():
        return now_iso()
    stopped = meeting.started_at + timedelta(seconds=recorded_s(me_wav))
    return stopped.isoformat(timespec="seconds")


def recover(meeting: Meeting, min_meeting_s: float) -> None:
    """Bring a meeting the daemon lost track of (crash, restart) back to the queue, or drop it if short."""
    if meeting.status in {"recording", "pause"}:
        for wav in meeting.path.glob("*.wav"):
            repair_wav(wav)
        meeting.update(status=QUEUED, stopped_at=meeting.meta["stopped_at"] or recovered_stop(meeting))
        if meeting.duration_s < min_meeting_s:
            log.info("discarding short recovered meeting %s", meeting.path.name)
            shutil.rmtree(meeting.path)
    elif meeting.status == "processing":
        meeting.update(status=QUEUED)


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

    def __init__(self, min_meeting_s: float) -> None:
        self.min_meeting_s = min_meeting_s
        self.pending: deque[Path] = deque()
        self.worker: subprocess.Popen[bytes] | None = None
        self.current: Path | None = None
        self.suspended = False
        self.run_s: float = 0
        self.budget_s: float = 0
        self.last_pump: float = 0

    def enqueue(self, path: Path) -> None:
        if path not in self.pending:
            self.pending.append(path)

    def scan(self, recordings_dir: Path, recording: Path | None) -> None:
        for meeting in list_meetings(recordings_dir):
            if meeting.path in {recording, self.current}:
                continue
            recover(meeting, self.min_meeting_s)
            if meeting.status == QUEUED and meeting.path.exists():
                self.enqueue(meeting.path)

    def pump(self, now: float, may_start: bool) -> None:
        elapsed = now - self.last_pump
        self.last_pump = now
        if self.worker and self.worker.poll() is None:
            self.charge(elapsed)
            return
        if self.worker:
            self.finish(self.worker.returncode)
        if may_start and self.pending:
            self.start(self.pending.popleft())

    def charge(self, elapsed: float) -> None:
        """Hang guard on running time only: a suspended worker is not using its budget."""
        if self.suspended:
            return
        self.run_s += elapsed
        if self.run_s > self.budget_s:
            log.error(
                "worker for %s ran %.0f s, over its %.0f s budget; killing it", self.current, self.run_s, self.budget_s
            )
            self.signal_worker(signal.SIGKILL)

    def start(self, path: Path) -> None:
        log.info("processing %s", path)
        self.current = path
        self.run_s = 0
        self.budget_s = BASE_BUDGET_S + Meeting.load(path).duration_s
        command = [*NICE, sys.executable, "-m", "meetrec.process", "meeting", str(path)]
        # Own process group, so suspend() stops the transcription children too.
        self.worker = subprocess.Popen(command, start_new_session=True)

    def signal_worker(self, signum: signal.Signals) -> None:
        if self.worker and self.worker.poll() is None:
            os.killpg(self.worker.pid, signum)

    def suspend(self) -> None:
        """A call started: keep the iGPU and CPU for it until the meeting is over.

        The summary stage only waits on the network, and its claude timeout would keep
        running while stopped, so a worker in that stage is left alone.
        """
        if self.current is None or Meeting.load(self.current).meta.get("stage") == "summary":
            return
        self.signal_worker(signal.SIGSTOP)
        self.suspended = True

    def resume(self) -> None:
        if self.suspended:
            self.signal_worker(signal.SIGCONT)
            self.suspended = False

    def finish(self, returncode: int) -> None:
        meeting = Meeting.load(self.current) if self.current else None
        self.worker = None
        self.current = None
        self.suspended = False
        if meeting is None:
            return
        if returncode and meeting.status in UNFINISHED:
            meeting.update(status="error", error=f"worker exited with {returncode}")
        notify(outcome(meeting))
