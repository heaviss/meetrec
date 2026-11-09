import logging
import os
import signal
import subprocess
import sys
from collections import deque
from pathlib import Path

from meetrec.meeting import Meeting, Outcome, list_meetings
from meetrec.notify import notify

log = logging.getLogger(__name__)

NICE = ("nice", "-n", "19")
BASE_BUDGET_S = 900  # plus the summarizer's timeout and the meeting duration


def outcome(meeting: Meeting) -> str:
    folder = meeting.path
    match meeting.outcome():
        case Outcome.error:
            return f"Ошибка обработки {folder.name}: {meeting.error}"
        case Outcome.summary:
            return f"Саммари готово: {meeting.summary}"
    return f"Транскрипт готов, саммари не сделано: {meeting.transcript}"


class Processing:
    """FIFO of closed meetings and the one worker process that handles them."""

    def __init__(self, min_meeting_s: float, summary_timeout_s: float = 900) -> None:
        self.min_meeting_s = min_meeting_s
        self.summary_timeout_s = summary_timeout_s
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
            if meeting.recover(self.min_meeting_s):
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
        self.budget_s = BASE_BUDGET_S + self.summary_timeout_s + Meeting.load(path).duration_s
        command = [*NICE, sys.executable, "-m", "meetrec.process", "meeting", str(path)]
        # Own process group, so suspend() stops the transcription children too.
        self.worker = subprocess.Popen(command, start_new_session=True)

    def signal_worker(self, signum: signal.Signals) -> None:
        if self.worker and self.worker.poll() is None:
            os.killpg(self.worker.pid, signum)

    def suspend(self) -> None:
        """A call started: keep the iGPU and CPU for it until the meeting is over.

        The summarizer's timeout would keep running while stopped, so a worker in the summary
        stage is left alone, even when a local summarizer competes with the call.
        """
        if self.current is None or Meeting.load(self.current).stage == "summary":
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
        if returncode:
            meeting.worker_died(returncode)
        notify(outcome(meeting))
