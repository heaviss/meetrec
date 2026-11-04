import subprocess
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from meetrec import processing
from meetrec.meeting import Meeting

STARTED = datetime.fromisoformat("2026-11-04T09:00:00+04:00")
MIN_MEETING_S = 120


def proc_state(pid: int) -> str:
    return Path(f"/proc/{pid}/stat").read_text().split(") ")[1][0]


@pytest.fixture
def sleeper() -> Iterator[subprocess.Popen[bytes]]:
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    yield proc
    proc.kill()
    proc.wait()


@pytest.mark.parametrize(("stage", "stopped"), [("transcribe", True), ("summary", False)])
def test_suspend_spares_summary_stage(
    tmp_path: Path, sleeper: subprocess.Popen[bytes], stage: str, stopped: bool
) -> None:
    meeting = Meeting.create(tmp_path, STARTED)
    meeting.update(status="processing", stage=stage)
    worker = processing.Processing(MIN_MEETING_S)
    worker.current = meeting.path
    worker.worker = sleeper

    worker.suspend()
    time.sleep(0.1)

    assert (proc_state(sleeper.pid) == "T") is stopped
    worker.resume()


def test_budget_kills_only_running_time(sleeper: subprocess.Popen[bytes]) -> None:
    worker = processing.Processing(MIN_MEETING_S)
    worker.worker = sleeper
    worker.budget_s = 10
    worker.suspended = True

    worker.charge(60)
    assert sleeper.poll() is None

    worker.suspended = False
    worker.charge(60)
    assert sleeper.wait(timeout=5) < 0
