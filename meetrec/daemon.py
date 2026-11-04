import json
import logging
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from meetrec import detect
from meetrec.config import Config
from meetrec.meeting import Meeting, list_meetings, repair_wav
from meetrec.notify import notify
from meetrec.record import Recorder
from meetrec.transcript import ts

log = logging.getLogger(__name__)
SILENCE_CHECK_S = 10


class Lifecycle:
    """Idle → recording ⇄ pause → close | discard. Time is passed in, so it can be tested without sleeping."""

    def __init__(self, pause_s: float, min_meeting_s: float):
        self.pause_s, self.min_meeting_s = pause_s, min_meeting_s
        self.state = "idle"
        self.started = self.released = 0.0

    def update(self, call_on: bool, now: float) -> str | None:
        match self.state:
            case "idle" if call_on:
                self.state, self.started = "recording", now
                return "start"
            case "recording" if not call_on:
                self.state, self.released = "pause", now
                return "pause"
            case "pause" if call_on:
                self.state = "recording"
                return "resume"
            case "pause" if now - self.released >= self.pause_s:
                self.state = "idle"
                return "close" if self.released - self.started >= self.min_meeting_s else "discard"
        return None


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Daemon:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.events: queue.Queue[str] = queue.Queue()
        self.life = Lifecycle(cfg.pause_s, cfg.min_meeting_s)
        self.streams: list[dict] = []
        self.port: dict | None = None
        self.meeting: Meeting | None = None
        self.recorder: Recorder | None = None
        self.silent_s = 0
        self.next_silence_check = 0.0
        self.pending: deque[Path] = deque()
        self.worker: subprocess.Popen | None = None
        self.worker_path: Path | None = None
        self.rescan = True
        self.last_state: dict | None = None

    def run(self) -> None:
        signal.signal(signal.SIGUSR1, lambda *_: self.request_rescan())
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        self.cfg.recordings_dir.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=detect.subscribe, args=(self.events,), daemon=True).start()
        self.events.put("mic")
        self.events.put("sink")
        log.info("meetrec daemon started, pause %ss", self.cfg.pause_s)
        try:
            while True:
                try:
                    event = self.events.get(timeout=1)
                except queue.Empty:
                    event = "tick"
                self.handle(event, time.monotonic())
        finally:
            self.shutdown()

    def request_rescan(self) -> None:
        self.rescan = True
        self.events.put("tick")

    def handle(self, event: str, now: float) -> None:
        if event == "mic":
            self.streams = detect.mic_streams(self.cfg.app_denylist)
        elif event == "sink":
            self.port = detect.default_port()
        if action := self.life.update(bool(self.streams), now):
            getattr(self, f"on_{action}")()
        if self.meeting:
            self.note_apps()
            self.note_port()
            self.watch_silence(now)
        if self.rescan:
            self.scan()
        self.pump_worker()
        self.write_state()

    def on_start(self) -> None:
        self.meeting = Meeting.create(self.cfg.recordings_dir, datetime.now().astimezone())
        self.recorder = Recorder(self.meeting.path)
        self.silent_s, self.next_silence_check = 0, time.monotonic() + SILENCE_CHECK_S
        apps = ", ".join(sorted({a["binary"] or a["name"] or "?" for a in map(detect.app_of, self.streams)}))
        notify(f"Запись встречи: {apps}")

    def on_pause(self) -> None:
        self.meeting.update(status="pause")

    def on_resume(self) -> None:
        self.meeting.update(status="recording")

    def on_close(self) -> None:
        meeting = self.stop_recording()
        notify(f"Встреча записана: {ts(meeting.duration_s * 1000)}")

    def on_discard(self) -> None:
        meeting, self.meeting = self.meeting, None
        self.recorder.stop()
        self.recorder = None
        shutil.rmtree(meeting.path)
        log.info("discarded short meeting %s", meeting.path.name)

    def stop_recording(self) -> Meeting:
        meeting, self.meeting = self.meeting, None
        gaps = self.recorder.stop()
        self.recorder = None
        meeting.update(status="queued", stopped_at=now_iso(), gaps=gaps)
        self.pending.append(meeting.path)
        return meeting

    def note_apps(self) -> None:
        known = {(a["binary"], a["name"]) for a in self.meeting.meta["apps"]}
        new = [a for a in map(detect.app_of, self.streams) if (a["binary"], a["name"]) not in known]
        if new:
            unique = {(a["binary"], a["name"]): {**a, "first_seen": now_iso()} for a in new}
            self.meeting.update(apps=[*self.meeting.meta["apps"], *unique.values()])

    def note_port(self) -> None:
        ports = self.meeting.meta["ports"]
        if self.port and (
            not ports or (ports[-1]["sink"], ports[-1]["port"]) != (self.port["sink"], self.port["port"])
        ):
            self.meeting.update(ports=[*ports, {"at": now_iso(), **self.port}])

    def watch_silence(self, now: float) -> None:
        if self.life.state != "recording" or now < self.next_silence_check:
            return
        self.next_silence_check = now + SILENCE_CHECK_S
        self.silent_s = self.silent_s + SILENCE_CHECK_S if self.recorder.mic_silent(SILENCE_CHECK_S) else 0
        if self.silent_s == self.cfg.silent_mic_s // SILENCE_CHECK_S * SILENCE_CHECK_S:
            notify(f"Микрофон молчит {self.silent_s} с — проверьте устройство")
            self.meeting.update(
                warnings=[*self.meeting.meta["warnings"], f"mic silent {self.silent_s} s at {now_iso()}"]
            )

    def scan(self) -> None:
        self.rescan = False
        current = self.meeting.path if self.meeting else None
        for meeting in list_meetings(self.cfg.recordings_dir):
            if meeting.path in (current, self.worker_path):
                continue
            if meeting.status in ("recording", "pause"):
                for wav in meeting.path.glob("*.wav"):
                    repair_wav(wav)
                meeting.update(status="queued", stopped_at=meeting.meta["stopped_at"] or now_iso())
            elif meeting.status == "processing":
                meeting.update(status="queued")
            if meeting.status == "queued" and meeting.path not in self.pending:
                self.pending.append(meeting.path)

    def pump_worker(self) -> None:
        if self.worker:
            if self.worker.poll() is None:
                return
            meeting = Meeting.load(self.worker_path)
            if meeting.status == "processing":
                meeting.update(status="error", error=f"worker exited with {self.worker.returncode}")
            if meeting.status == "error":
                notify(f"Ошибка обработки {meeting.path.name}: {meeting.meta['error']}")
            elif meeting.meta["summary_done"]:
                notify(f"Саммари готово: {meeting.path / 'summary.md'}")
            else:
                notify(f"Транскрипт готов, саммари не сделано: {meeting.path / 'transcript.md'}")
            self.worker = self.worker_path = None
        if self.life.state == "idle" and self.pending:
            self.worker_path = self.pending.popleft()
            log.info("processing %s", self.worker_path)
            self.worker = subprocess.Popen(
                ["nice", "-n", "19", sys.executable, "-m", "meetrec.process", "meeting", str(self.worker_path)],
            )

    def write_state(self) -> None:
        state = {
            "state": self.life.state,
            "meeting": str(self.meeting.path) if self.meeting else None,
            "processing": str(self.worker_path) if self.worker_path else None,
            "queue": [str(p) for p in self.pending],
        }
        if state != self.last_state:
            self.cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.cfg.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1))
            self.last_state = state

    def shutdown(self) -> None:
        if self.recorder:
            log.info("stopping, queueing the meeting in progress")
            self.stop_recording()
        self.cfg.state_path.unlink(missing_ok=True)
