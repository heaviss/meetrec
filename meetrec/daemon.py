import logging
import signal
import threading
import time
from contextlib import closing

from meetrec.config import Config
from meetrec.lifecycle import Action, State
from meetrec.meeting import write_json
from meetrec.notify import notify
from meetrec.pactl import Pactl, Snapshot
from meetrec.processing import Processing
from meetrec.watcher import Change, Watcher

log = logging.getLogger(__name__)


class Daemon:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.pactl = Pactl(cfg.app_denylist)
        self.watcher = Watcher(cfg)
        self.processing = Processing(cfg.min_meeting_s)
        self.rescan_requested = True
        self.last_state: dict[str, object] = {}
        self.stop = threading.Event()

    def run(self) -> None:
        self.install_signals()
        self.cfg.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.pactl.start(self.stop)
        log.info("meetrec daemon started, pause %ss", self.cfg.pause_s)
        if self.cfg.echo_cancel and not (self.cfg.localvqe_lib.exists() and self.cfg.localvqe_model.exists()):
            notify("эхо не подавляется: запустите meetrec setup")
        with closing(self):
            while not self.stop.is_set():
                self.on_snapshot(self.pactl.next(), time.monotonic())

    def install_signals(self) -> None:
        signal.signal(signal.SIGUSR1, self.request_rescan)
        # Event.set takes no lock the main thread can hold; the loop sees it within a second.
        signal.signal(signal.SIGTERM, lambda *_: self.stop.set())

    def request_rescan(self, *_: object) -> None:
        # Only a flag: queue.Queue is not reentrant, so a signal handler must not touch it.
        self.rescan_requested = True

    def on_snapshot(self, snapshot: Snapshot, now: float) -> None:
        # systemd stops the whole cgroup at once: pw-record dying then is ours, not a fault; close() takes over.
        if not self.stop.is_set():
            self.act(self.watcher.update(*snapshot, now))
        recording = self.watcher.meeting
        if self.rescan_requested:
            self.rescan_requested = False
            self.processing.scan(self.cfg.recordings_dir, recording.path if recording else None)
        self.processing.pump(now, may_start=self.watcher.state == State.idle)
        self.write_state()

    def act(self, change: Change | None) -> None:
        """A call holds the iGPU and CPU: the worker waits while a meeting is being recorded."""
        match change:
            case (Action.start, _):
                self.processing.suspend()
            case (Action.close, meeting):
                self.processing.enqueue(meeting.path)
                self.processing.resume()
            case (Action.discard, _):
                self.processing.resume()

    def write_state(self) -> None:
        state: dict[str, object] = {
            "state": self.watcher.state,
            "meeting": str(self.watcher.meeting.path) if self.watcher.meeting else None,
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
        self.watcher.stop(time.monotonic())
        self.processing.resume()
        self.cfg.state_path.unlink(missing_ok=True)
