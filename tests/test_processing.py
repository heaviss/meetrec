import wave
from datetime import datetime
from pathlib import Path

import pytest

from meetrec import processing
from meetrec.meeting import Meeting, list_meetings

STARTED = datetime.fromisoformat("2026-11-04T09:00:00+04:00")
RATE = 16000
MIN_MEETING_S = 120
SECONDS = 600


def write_me_wav(meeting: Meeting, seconds: int) -> None:
    with wave.open(str(meeting.path / "me.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(bytes(2 * RATE * seconds))


def test_recovered_meeting_ends_with_recording(tmp_path: Path) -> None:
    meeting = Meeting.create(tmp_path, STARTED)
    write_me_wav(meeting, SECONDS)

    processing.recover(meeting, MIN_MEETING_S)

    assert meeting.status == "queued"
    assert meeting.duration_s == SECONDS


def test_short_recovered_meeting_is_dropped(tmp_path: Path) -> None:
    meeting = Meeting.create(tmp_path, STARTED)
    write_me_wav(meeting, 20)

    processing.recover(meeting, MIN_MEETING_S)

    assert not meeting.path.exists()


def test_crash_during_pause_keeps_release_moment(tmp_path: Path) -> None:
    meeting = Meeting.create(tmp_path, STARTED)
    meeting.update(status="pause", stopped_at="2026-11-04T09:10:00+04:00")

    processing.recover(meeting, MIN_MEETING_S)

    assert meeting.status == "queued"
    assert meeting.duration_s == SECONDS


def test_worker_dying_before_work_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(processing, "notify", sent.append)
    meeting = Meeting.create(tmp_path, STARTED)
    meeting.update(status="queued")
    worker = processing.Processing(MIN_MEETING_S)
    worker.current = meeting.path

    worker.finish(returncode=1)

    folder = meeting.path.name
    assert Meeting.load(meeting.path).status == "error"
    assert sent == [f"Ошибка обработки {folder}: worker exited with 1"]


def test_broken_meta_is_skipped(tmp_path: Path) -> None:
    good = Meeting.create(tmp_path, STARTED)
    broken = tmp_path / "junk"
    broken.mkdir()
    (broken / "meta.json").write_text("{}")

    assert [meeting.path for meeting in list_meetings(tmp_path)] == [good.path]
