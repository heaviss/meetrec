import json
import logging
import queue
import signal
import sys
import threading
import time
from enum import StrEnum

from meetrec import detect, pactl_events
from meetrec.config import Config
from meetrec.processing import Processing
from meetrec.session import Session

log = logging.getLogger(__name__)


class State(StrEnum):
    idle = "idle"
    recording = "recording"
    pause = "pause"


class Action(StrEnum):
    start = "start"
    pause = "pause"
    resume = "resume"
    close = "close"
    discard = "discard"


class Lifecycle:
    """Idle → recording ⇄ pause → close | discard. Time is passed in, so it can be tested without sleeping."""

    def __init__(self, pause_s: float, min_meeting_s: float) -> None:
        self.pause_s = pause_s
        self.min_meeting_s = min_meeting_s
        self.state = State.idle
        self.started: float = 0
        self.released: float = 0

    def update(self, call_on: bool, now: float) -> Action | None:
        match self.state:
            case State.idle if call_on:
                self.state = State.recording
                self.started = now
                return Action.start
            case State.recording if not call_on:
                self.state = State.pause
                self.released = now
                return Action.pause
            case State.pause if call_on:
                self.state = State.recording
                return Action.resume
            case State.pause if now - self.released >= self.pause_s:
                self.state = State.idle
                long_enough = self.released - self.started >= self.min_meeting_s
                return Action.close if long_enough else Action.discard
        return None


def terminate(*_: object) -> None:
    sys.exit(0)


def active(session: Session | None) -> Session:
    if session is None:
        raise RuntimeError("no meeting in progress")
    return session


def next_event(events: queue.Queue[str]) -> str:
    try:
        return events.get(timeout=1)
    except queue.Empty:
        return "tick"


class Daemon:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.events: queue.Queue[str] = queue.Queue()
        self.life = Lifecycle(cfg.pause_s, cfg.min_meeting_s)
        self.streams: list[detect.Stream] = []
        self.port: dict[str, str | None] | None = None
        self.session: Session | None = None
        self.processing = Processing()
        self.rescan_requested = True
        self.last_state = ""
        self.running = True

    def run(self) -> None:
        self.install_signals()
        self.cfg.recordings_dir.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=pactl_events.subscribe, args=(self.events, threading.Event()), daemon=True).start()
        self.events.put("mic")
        self.events.put("sink")
        log.info("meetrec daemon started, pause %ss", self.cfg.pause_s)
        try:
            while self.running:
                self.on_event(next_event(self.events), time.monotonic())
        except KeyboardInterrupt, SystemExit:
            self.shutdown()
            raise

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
            if self.life.state == State.recording:
                self.session.watch_silence(now, self.cfg.silent_mic_s)
        if self.rescan_requested:
            self.rescan_requested = False
            self.processing.scan(self.cfg.recordings_dir, self.session.meeting.path if self.session else None)
        self.processing.pump(may_start=self.life.state == State.idle)
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
        state = json.dumps(
            {
                "state": self.life.state,
                "meeting": str(self.session.meeting.path) if self.session else None,
                "processing": str(self.processing.current) if self.processing.current else None,
                "queue": [str(path) for path in self.processing.pending],
            },
            ensure_ascii=False,
            indent=1,
        )
        if state != self.last_state:
            self.cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.cfg.state_path.write_text(state)
            self.last_state = state

    def shutdown(self) -> None:
        if self.session:
            log.info("stopping, queueing the meeting in progress")
            self.session.close()
            self.session = None
        self.processing.resume()
        self.cfg.state_path.unlink(missing_ok=True)
