import wave
from datetime import datetime
from pathlib import Path

import pytest

from meetrec import processing
from meetrec.meeting import Meeting, list_meetings

STARTED = datetime.fromisoformat("2026-11-04T09:00:00+04:00")
RATE = 16000
SECONDS = 90


def test_recovered_meeting_ends_with_recording(tmp_path: Path) -> None:
    meeting = Meeting.create(tmp_path, STARTED)
    with wave.open(str(meeting.path / "me.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(bytes(2 * RATE * SECONDS))

    processing.recover(meeting)

    assert meeting.status == "queued"
    assert meeting.duration_s == SECONDS


def test_crash_during_pause_keeps_release_moment(tmp_path: Path) -> None:
    meeting = Meeting.create(tmp_path, STARTED)
    meeting.update(status="pause", stopped_at="2026-11-04T09:10:00+04:00")

    processing.recover(meeting)

    assert meeting.status == "queued"
    assert meeting.duration_s == 600


def test_worker_dying_before_work_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(processing, "notify", sent.append)
    meeting = Meeting.create(tmp_path, STARTED)
    meeting.update(status="queued")
    queue = processing.Processing()
    queue.current = meeting.path

    queue.finish(returncode=1)

    assert Meeting.load(meeting.path).status == "error"
    folder = meeting.path.name
    assert sent == [f"Ошибка обработки {folder}: worker exited with 1"]


def test_broken_meta_is_skipped(tmp_path: Path) -> None:
    good = Meeting.create(tmp_path, STARTED)
    broken = tmp_path / "junk"
    broken.mkdir()
    (broken / "meta.json").write_text("{}")

    assert [meeting.path for meeting in list_meetings(tmp_path)] == [good.path]
