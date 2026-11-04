import logging
from collections.abc import Callable
from datetime import datetime

from meetrec import notify as notify_module
from meetrec.config import Config
from meetrec.lifecycle import Action, Lifecycle, State
from meetrec.meeting import Meeting
from meetrec.pactl import Port, Stream, app_of
from meetrec.record import PwRecorder, Recorder
from meetrec.session import Notify, Session
from meetrec.transcript import MS_PER_S, clock

log = logging.getLogger(__name__)

Change = tuple[Action, Meeting]


def app_label(app: dict[str, str | None]) -> str:
    return app["binary"] or app["name"] or "?"


class Watcher:
    """Turns what pactl shows into meetings: starts, pauses, closes or discards them, and watches the recording.

    Time is passed in, and the recorder and notifications are plugged in, so it runs in tests without PipeWire.
    """

    def __init__(
        self,
        cfg: Config,
        notify: Notify = notify_module.notify,
        start_recorder: Callable[[Meeting], Recorder] = PwRecorder,
    ) -> None:
        self.cfg = cfg
        self.notify = notify
        self.start_recorder = start_recorder
        self.life = Lifecycle(cfg.pause_s, cfg.min_meeting_s)
        self.session: Session | None = None

    @property
    def state(self) -> State:
        return self.life.state

    @property
    def meeting(self) -> Meeting | None:
        return self.session.meeting if self.session else None

    def update(self, streams: list[Stream], port: Port | None, now: float) -> Change | None:
        """The microphone streams and the output port as of now; what happened to the meeting, if anything."""
        action = self.life.update(bool(streams), now)
        change = self.act(action, streams, now) if action else None
        if self.session:
            self.session.note_apps(streams)
            self.session.note_port(port)
            self.session.watch_recorder()
            if self.life.state == State.recording:
                self.session.watch_silence(now, self.cfg.silent_mic_s)
        return change

    def stop(self, now: float) -> None:
        """The daemon is stopping mid-meeting: keep the meeting by the same rule as a normal close."""
        if self.session is None:
            return
        session = self.detach()
        if self.life.meeting_length(now) < self.cfg.min_meeting_s:
            log.info("stopping, discarding the short meeting in progress")
            session.discard()
            return
        log.info("stopping, queueing the meeting in progress")
        session.close()

    def act(self, action: Action, streams: list[Stream], now: float) -> Change:
        if action == Action.start:
            return action, self.start(streams, now)
        session = self.session
        if session is None:
            raise RuntimeError("no meeting in progress")
        match action:
            case Action.pause:
                session.meeting.pause()
            case Action.resume:
                session.meeting.resume()
            case Action.close:
                self.detach().close()
                self.notify(f"Встреча записана: {clock(session.meeting.duration_s * MS_PER_S)}")
            case Action.discard:
                self.detach().discard()
        return action, session.meeting

    def start(self, streams: list[Stream], now: float) -> Meeting:
        meeting = Meeting.create(self.cfg.recordings_dir, datetime.now().astimezone())
        self.session = Session(meeting, self.start_recorder(meeting), self.notify, now)
        apps = ", ".join(sorted({app_label(app_of(stream)) for stream in streams}))
        self.notify(f"Запись встречи: {apps}")
        return meeting

    def detach(self) -> Session:
        """Unhook the session before closing it, so a stop arriving mid-close cannot touch it again."""
        session = self.session
        if session is None:
            raise RuntimeError("no meeting in progress")
        self.session = None
        return session
