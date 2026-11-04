import wave
from pathlib import Path

import pytest

from meetrec.meeting import Meeting, Status, list_meetings

RATE = 16000
MIN_MEETING_S = 120
SECONDS = 600


def write_me_wav(meeting: Meeting, seconds: int) -> None:
    with wave.open(str(meeting.path / "me.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(bytes(2 * RATE * seconds))


def test_recovered_meeting_ends_with_recording(meeting: Meeting) -> None:
    write_me_wav(meeting, SECONDS)

    assert meeting.recover(MIN_MEETING_S)
    assert meeting.status == Status.queued
    assert meeting.duration_s == SECONDS


def test_short_recovered_meeting_is_dropped(meeting: Meeting) -> None:
    write_me_wav(meeting, 20)

    assert not meeting.recover(MIN_MEETING_S)
    assert not meeting.path.exists()


def test_crash_during_pause_keeps_release_moment(meeting: Meeting) -> None:
    meeting.update(stopped_at="2026-11-04T09:10:00+04:00", status=Status.pause)

    assert meeting.recover(MIN_MEETING_S)
    assert meeting.duration_s == SECONDS


@pytest.mark.parametrize(("status", "waits"), [(Status.processing, True), (Status.done, False), (Status.error, False)])
def test_recover_requeues_only_interrupted_work(meeting: Meeting, status: Status, waits: bool) -> None:
    meeting.update(status=status)

    assert meeting.recover(MIN_MEETING_S) is waits


def test_broken_meta_is_skipped(tmp_path: Path, meeting: Meeting) -> None:
    broken = tmp_path / "junk"
    broken.mkdir()
    (broken / "meta.json").write_text("{}")

    assert [listed.path for listed in list_meetings(tmp_path)] == [meeting.path]
