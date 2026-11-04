from datetime import datetime
from pathlib import Path
from typing import cast

import pytest

from meetrec import session as session_module
from meetrec.daemon import stop_session
from meetrec.meeting import Meeting
from meetrec.record import Recorder
from meetrec.session import Session

STARTED = datetime.fromisoformat("2026-11-04T09:00:00+04:00")
MIN_MEETING_S = 120


class FakeRecorder:
    def __init__(self, dead: set[str]) -> None:
        self.dead = dead

    def stop(self) -> list[dict[str, object]]:
        return []

    def dead_tracks(self) -> set[str]:
        return self.dead


def fake_session(folder: Path, dead: tuple[str, ...] = ()) -> Session:
    session = Session.__new__(Session)
    session.meeting = Meeting.create(folder, STARTED)
    session.recorder = cast(Recorder, FakeRecorder(set(dead)))
    session.dead_tracks = set()
    return session


def test_stop_keeps_a_meeting_already_closed(tmp_path: Path) -> None:
    session = fake_session(tmp_path)
    session.close()

    stop_session(session, 0, MIN_MEETING_S)

    assert session.meeting.path.exists()


def test_stop_discards_short_meeting(tmp_path: Path) -> None:
    session = fake_session(tmp_path)

    stop_session(session, 10, MIN_MEETING_S)

    assert not session.meeting.path.exists()


def test_stop_queues_long_meeting(tmp_path: Path) -> None:
    session = fake_session(tmp_path)

    stop_session(session, 300, MIN_MEETING_S)

    assert Meeting.load(session.meeting.path).status == "queued"


def test_dead_track_is_reported_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(session_module, "notify", sent.append)
    session = fake_session(tmp_path, ("me",))

    session.watch_recorder()
    session.watch_recorder()

    assert len(sent) == 1
    assert len(Meeting.load(session.meeting.path).meta["warnings"]) == 1
