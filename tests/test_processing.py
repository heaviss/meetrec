import wave
from datetime import datetime
from pathlib import Path

from meetrec.meeting import Meeting
from meetrec.processing import recover

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

    recover(meeting)

    assert meeting.status == "queued"
    assert meeting.duration_s == SECONDS
