from pathlib import Path

import pytest

from meetrec.config import Config
from meetrec.daemon import Daemon
from meetrec.lifecycle import Action
from meetrec.meeting import Meeting, Status
from meetrec.pactl import Port, Snapshot, Stream
from meetrec.watcher import Watcher

SILENT_MIC_S = 60


class FakeRecorder:
    def __init__(self, dead: set[str], silent: bool) -> None:
        self.dead = dead
        self.silent = silent
        self.stopped = False

    def stop(self) -> list[dict[str, object]]:
        self.stopped = True
        return []

    def dead_tracks(self) -> set[str]:
        return self.dead

    def mic_silent(self, seconds: int) -> bool:
        return self.silent


class Rig:
    """A watcher over a temp folder, with a fake recorder and the notifications it sent."""

    def __init__(self, folder: Path, dead: tuple[str, ...] = (), silent: bool = False) -> None:
        self.sent: list[str] = []
        self.streams: list[Stream] = [
            {"properties": {"application.process.binary": "firefox", "application.name": "Firefox"}},
        ]
        self.port: Port = {"sink": "alsa_output.pci", "port": "[Out] Speaker"}
        self.recorder = FakeRecorder(set(dead), silent)
        cfg = Config(recordings_dir=folder, data_dir=folder, silent_mic_s=SILENT_MIC_S)
        self.watcher = Watcher(cfg, notify=self.sent.append, start_recorder=lambda _: self.recorder)

    def run(self, timeline: list[tuple[float, bool]]) -> list[tuple[Action, Meeting]]:
        changes = [self.update(now, call_on) for now, call_on in timeline]
        return [change for change in changes if change]

    def update(self, now: float, call_on: bool) -> tuple[Action, Meeting] | None:
        return self.watcher.update(self.streams if call_on else [], self.port, now)


def test_call_is_recorded_and_queued(tmp_path: Path) -> None:
    rig = Rig(tmp_path)

    paused_and_back = [(0, True), (100, False), (110, True)]
    changes = rig.run([*paused_and_back, (300, False), (330, False)])

    actions = [action for action, _ in changes]
    assert actions == ["start", "pause", "resume", "pause", "close"]
    assert Meeting.load(changes[-1][1].path).status == Status.queued
    assert rig.recorder.stopped
    assert rig.watcher.meeting is None


def test_meeting_notes_apps_and_ports(tmp_path: Path) -> None:
    rig = Rig(tmp_path)

    meeting = rig.run([(0, True), (1, True)])[0][1]

    assert rig.sent == ["Запись встречи: firefox"]
    assert meeting.meta["apps"][0]["binary"] == "firefox"
    assert meeting.meta["ports"] == [{**meeting.meta["ports"][0], **rig.port}]


def test_short_call_is_discarded(tmp_path: Path) -> None:
    rig = Rig(tmp_path)

    changes = rig.run([(0, True), (60, False), (90, False)])

    assert changes[-1][0] == Action.discard
    assert not changes[-1][1].path.exists()


def test_dead_track_is_reported_once(tmp_path: Path) -> None:
    rig = Rig(tmp_path, dead=("me",))

    rig.run([(0, True), (1, True), (2, True)])

    assert rig.sent[1:] == ["Запись me оборвалась — встреча пишется не полностью"]
    assert rig.watcher.meeting
    assert len(rig.watcher.meeting.meta["warnings"]) == 1


def test_silent_mic_is_reported_once(tmp_path: Path) -> None:
    rig = Rig(tmp_path, silent=True)

    rig.run([(now, True) for now in range(0, 2 * SILENT_MIC_S, 10)])

    assert rig.sent[1:] == [f"Микрофон молчит {SILENT_MIC_S} с — проверьте устройство"]


@pytest.mark.parametrize(("stopped_at", "kept"), [(10, False), (300, True)])
def test_stop_keeps_meeting_by_close_rule(tmp_path: Path, stopped_at: float, kept: bool) -> None:
    rig = Rig(tmp_path)
    meeting = rig.run([(0, True)])[0][1]

    rig.watcher.stop(stopped_at)

    assert meeting.path.exists() is kept
    assert rig.watcher.meeting is None


def test_stopping_daemon_ignores_killed_tracks(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    daemon = Daemon(Config(recordings_dir=tmp_path, data_dir=tmp_path))
    daemon.watcher = rig.watcher
    daemon.on_snapshot(Snapshot(rig.streams, rig.port), 0)
    rig.sent.clear()
    daemon.stop.set()
    rig.recorder.dead.update({"me", "them"})

    daemon.on_snapshot(Snapshot(rig.streams, rig.port), 1)

    assert rig.sent == []
