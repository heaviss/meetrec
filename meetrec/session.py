import shutil
import time
from datetime import datetime
from pathlib import Path

from meetrec.detect import Stream, app_of
from meetrec.meeting import Meeting, now_iso
from meetrec.notify import notify
from meetrec.record import Recorder
from meetrec.transcript import MS_PER_S, clock

SILENCE_CHECK_S = 10


def app_label(app: dict[str, str | None]) -> str:
    return app["binary"] or app["name"] or "?"


def same_port(seen: dict[str, str | None], port: dict[str, str | None]) -> bool:
    return seen["sink"] == port["sink"] and seen["port"] == port["port"]


class Session:
    """One meeting being recorded: its folder, the two pw-record processes and what they saw."""

    def __init__(self, recordings_dir: Path, streams: list[Stream]) -> None:
        self.meeting = Meeting.create(recordings_dir, datetime.now().astimezone())
        self.recorder = Recorder(self.meeting.path)
        self.silent_s = 0
        self.silence_warned = False
        self.dead_tracks: set[str] = set()
        self.next_silence_check = time.monotonic() + SILENCE_CHECK_S
        apps = ", ".join(sorted({app_label(app_of(stream)) for stream in streams}))
        notify(f"Запись встречи: {apps}")

    def pause(self) -> None:
        """stopped_at is the release moment, kept on disk so a crash during the pause keeps it."""
        self.meeting.update(status="pause", stopped_at=now_iso())

    def resume(self) -> None:
        self.meeting.update(status="recording", stopped_at=None)

    def close(self) -> Meeting:
        """The meeting ends when the microphone was released, not when the pause ran out."""
        gaps = self.recorder.stop()
        self.meeting.update(status="queued", stopped_at=self.meeting.meta["stopped_at"] or now_iso(), gaps=gaps)
        return self.meeting

    def close_and_report(self) -> Meeting:
        meeting = self.close()
        notify(f"Встреча записана: {clock(meeting.duration_s * MS_PER_S)}")
        return meeting

    def discard(self) -> None:
        self.recorder.stop()
        shutil.rmtree(self.meeting.path)

    def note_apps(self, streams: list[Stream]) -> None:
        known = {(app["binary"], app["name"]) for app in self.meeting.meta["apps"]}
        fresh = {(app["binary"], app["name"]): app for app in map(app_of, streams)}
        new_apps = [{**app, "first_seen": now_iso()} for key, app in fresh.items() if key not in known]
        if new_apps:
            self.meeting.append("apps", *new_apps)

    def note_port(self, port: dict[str, str | None] | None) -> None:
        ports = self.meeting.meta["ports"]
        if port is None or (ports and same_port(ports[-1], port)):
            return
        self.meeting.append("ports", {"at": now_iso(), **port})

    def watch_recorder(self) -> None:
        for track in self.recorder.dead_tracks() - self.dead_tracks:
            self.dead_tracks.add(track)
            notify(f"Запись {track} оборвалась — встреча пишется не полностью")
            self.meeting.append("warnings", f"pw-record {track} exited at {now_iso()}")

    def watch_silence(self, now: float, threshold_s: int) -> None:
        if self.silence_warned or now < self.next_silence_check:
            return
        self.next_silence_check = now + SILENCE_CHECK_S
        silent = self.recorder.mic_silent(SILENCE_CHECK_S)
        self.silent_s = self.silent_s + SILENCE_CHECK_S if silent else 0
        if self.silent_s >= max(threshold_s, SILENCE_CHECK_S):
            self.silence_warned = True
            notify(f"Микрофон молчит {self.silent_s} с — проверьте устройство")
            self.meeting.append("warnings", f"mic silent {self.silent_s} s at {now_iso()}")
