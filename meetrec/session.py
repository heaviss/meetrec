import shutil
from collections.abc import Callable

from meetrec.detect import Stream, app_of
from meetrec.meeting import Meeting, now_iso
from meetrec.record import Recorder

SILENCE_CHECK_S = 10

Notify = Callable[[str], None]


def same_port(seen: dict[str, str | None], port: dict[str, str | None]) -> bool:
    return seen["sink"] == port["sink"] and seen["port"] == port["port"]


class Session:
    """One meeting being recorded: its folder, its recorder and what they saw."""

    def __init__(self, meeting: Meeting, recorder: Recorder, notify: Notify, now: float) -> None:
        self.meeting = meeting
        self.recorder = recorder
        self.notify = notify
        self.silent_s = 0
        self.silence_warned = False
        self.dead_tracks: set[str] = set()
        self.next_silence_check = now + SILENCE_CHECK_S

    def close(self) -> Meeting:
        self.meeting.close(self.recorder.stop())
        return self.meeting

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
            self.notify(f"Запись {track} оборвалась — встреча пишется не полностью")
            self.meeting.append("warnings", f"pw-record {track} exited at {now_iso()}")

    def watch_silence(self, now: float, threshold_s: int) -> None:
        if self.silence_warned or now < self.next_silence_check:
            return
        self.next_silence_check = now + SILENCE_CHECK_S
        silent = self.recorder.mic_silent(SILENCE_CHECK_S)
        self.silent_s = self.silent_s + SILENCE_CHECK_S if silent else 0
        if self.silent_s >= max(threshold_s, SILENCE_CHECK_S):
            self.silence_warned = True
            self.notify(f"Микрофон молчит {self.silent_s} с — проверьте устройство")
            self.meeting.append("warnings", f"mic silent {self.silent_s} s at {now_iso()}")
