import logging
import signal
import sys
import threading
import time
from contextlib import closing

from meetrec import detect, pactl_events
from meetrec.config import Config
from meetrec.lifecycle import Action, Lifecycle, State
from meetrec.meeting import write_json
from meetrec.processing import Processing
from meetrec.session import Session

log = logging.getLogger(__name__)


def terminate(*_: object) -> None:
    sys.exit(0)


def active(session: Session | None) -> Session:
    if session is None:
        raise RuntimeError("no meeting in progress")
    return session


def stop_session(session: Session, length_s: float, min_meeting_s: float) -> None:
    """The daemon is stopping mid-meeting: keep the meeting by the same rule as a normal close."""
    if length_s < min_meeting_s:
        log.info("stopping, discarding the short meeting in progress")
        session.discard()
        return
    log.info("stopping, queueing the meeting in progress")
    session.close()


class Daemon:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.events = pactl_events.event_queue()
        self.life = Lifecycle(cfg.pause_s, cfg.min_meeting_s)
        self.streams: list[detect.Stream] = []
        self.port: dict[str, str | None] | None = None
        self.session: Session | None = None
        self.processing = Processing()
        self.rescan_requested = True
        self.last_state: dict[str, object] = {}
        self.stop = threading.Event()

    def run(self) -> None:
        self.install_signals()
        self.cfg.recordings_dir.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=pactl_events.subscribe, args=(self.events, self.stop), daemon=True).start()
        self.events.put("mic")
        self.events.put("sink")
        log.info("meetrec daemon started, pause %ss", self.cfg.pause_s)
        with closing(self):
            while not self.stop.is_set():
                self.on_event(pactl_events.next_event(self.events), time.monotonic())

    def install_signals(self) -> None:
        signal.signal(signal.SIGUSR1, self.request_rescan)
        signal.signal(signal.SIGTERM, terminate)

    def request_rescan(self, *_: object) -> None:
        # Only a flag: queue.Queue is not reentrant, so a signal handler must not touch it.
        self.rescan_requested = True

    def refresh(self, event: str) -> None:
        try:
            if event == "mic":
                self.streams = detect.mic_streams(self.cfg.app_denylist)
            elif event == "sink":
                self.port = detect.default_port()
        except detect.SNAPSHOT_ERRORS:
            log.exception("pactl snapshot failed, keeping the previous one")

    def on_event(self, event: str, now: float) -> None:
        self.refresh(event)
        self.act(self.life.update(bool(self.streams), now))
        if self.session:
            self.session.note_apps(self.streams)
            self.session.note_port(self.port)
            self.session.watch_recorder()
            if self.life.state == State.recording:
                self.session.watch_silence(now, self.cfg.silent_mic_s)
        if self.rescan_requested:
            self.rescan_requested = False
            self.processing.scan(self.cfg.recordings_dir, self.session.meeting.path if self.session else None)
        self.processing.pump(now, may_start=self.life.state == State.idle)
        self.write_state()

    def act(self, action: Action | None) -> None:
        match action:
            case Action.start:
                self.processing.suspend()
                self.session = Session(self.cfg.recordings_dir, self.streams)
            case Action.pause:
                active(self.session).pause()
            case Action.resume:
                active(self.session).resume()
            case Action.close:
                self.processing.enqueue(active(self.session).close_and_report().path)
                self.end_session()
            case Action.discard:
                active(self.session).discard()
                self.end_session()

    def end_session(self) -> None:
        self.session = None
        self.processing.resume()

    def write_state(self) -> None:
        state: dict[str, object] = {
            "state": self.life.state,
            "meeting": str(self.session.meeting.path) if self.session else None,
            "processing": str(self.processing.current) if self.processing.current else None,
            "queue": [str(path) for path in self.processing.pending],
        }
        if state != self.last_state:
            self.cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
            write_json(self.cfg.state_path, state)
            self.last_state = state

    def close(self) -> None:
        """Runs on any exit from the loop, SIGTERM and crashes alike."""
        self.stop.set()
        if self.session:
            stop_session(self.session, self.life.meeting_length(time.monotonic()), self.cfg.min_meeting_s)
            self.session = None
        self.processing.resume()
        self.cfg.state_path.unlink(missing_ok=True)
