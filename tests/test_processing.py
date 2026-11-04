from pathlib import Path

import pytest

from meetrec import processing
from meetrec.meeting import Meeting, Status

MIN_MEETING_S = 120


def test_worker_dying_before_work_is_an_error(meeting: Meeting, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(processing, "notify", sent.append)
    meeting.update(status=Status.queued)
    worker = processing.Processing(MIN_MEETING_S)
    worker.current = meeting.path

    worker.finish(returncode=1)

    folder = meeting.path.name
    assert Meeting.load(meeting.path).status == Status.error
    assert sent == [f"Ошибка обработки {folder}: worker exited with 1"]


def test_scan_queues_interrupted_meetings(tmp_path: Path, meeting: Meeting) -> None:
    meeting.update(status=Status.processing)
    worker = processing.Processing(MIN_MEETING_S)

    worker.scan(tmp_path, recording=None)

    assert list(worker.pending) == [meeting.path]
