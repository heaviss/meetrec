import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum, auto
from pathlib import Path
from typing import Any

from meetrec.audio import recorded_s, repair_wav

log = logging.getLogger(__name__)


class Status(StrEnum):
    """meta.json `status`, the one source of truth about where a meeting is."""

    recording = auto()
    pause = auto()
    queued = auto()
    processing = auto()
    done = auto()
    error = auto()


class Outcome(StrEnum):
    """What a finished meeting left behind."""

    error = auto()
    summary = auto()
    summary_skipped = auto()
    transcript_only = auto()


ACTIVE = frozenset((Status.recording, Status.pause, Status.processing))
LOST = frozenset((Status.recording, Status.pause))
UNFINISHED = frozenset((Status.queued, Status.processing))


@dataclass
class Meeting:
    path: Path
    meta: dict[str, Any]

    @classmethod
    def create(cls, recordings_dir: Path, now: datetime) -> Meeting:
        base = recordings_dir / now.strftime("%Y-%m-%d-%H%M")
        path = base
        suffix = 1
        while path.exists():
            suffix += 1
            path = base.with_name(f"{base.name}-{suffix}")
        path.mkdir(parents=True)
        meeting = cls(path, new_meta(now))
        meeting.save()
        return meeting

    @classmethod
    def load(cls, path: Path) -> Meeting:
        return cls(path, json.loads((path / "meta.json").read_text()))

    @property
    def status(self) -> Status:
        return Status(self.meta["status"])

    @property
    def error(self) -> str | None:
        error = self.meta["error"]
        return None if error is None else str(error)

    @property
    def stopped_at(self) -> str | None:
        """The moment the microphone was last released; None while it is held."""
        stopped = self.meta["stopped_at"]
        return None if stopped is None else str(stopped)

    @property
    def redo(self) -> str:
        return self.meta.get("redo") or "missing"

    @property
    def stage(self) -> str | None:
        return self.meta.get("stage")

    @property
    def summary_done(self) -> bool:
        return bool(self.meta["summary_done"])

    @property
    def started_at(self) -> datetime:
        return datetime.fromisoformat(self.meta["started_at"])

    @property
    def duration_s(self) -> float:
        if not self.stopped_at:
            return 0
        return (datetime.fromisoformat(self.stopped_at) - self.started_at).total_seconds()

    def save(self) -> None:
        write_json(self.path / "meta.json", self.meta)

    def checked(self) -> Meeting:
        """Fail on a meta.json without the one field every listing sorts by."""
        datetime.fromisoformat(str(self.meta.get("started_at")))
        return self

    def update(self, **fields: Any) -> None:
        self.meta.update(fields)
        self.save()

    def append(self, key: str, *entries: Any) -> None:
        self.update(**{key: [*self.meta[key], *entries]})

    def pause(self) -> None:
        """stopped_at is the release moment, kept on disk so a crash during the pause keeps it."""
        self.update(status=Status.pause, stopped_at=now_iso())

    def resume(self) -> None:
        self.update(status=Status.recording, stopped_at=None)

    def close(self, gaps: list[dict[str, object]]) -> None:
        """The meeting ends when the microphone was released, not when the pause ran out."""
        self.update(status=Status.queued, stopped_at=self.stopped_at or now_iso(), gaps=gaps)

    def queue(self, redo: str, language: str | None = None) -> None:
        if self.status in ACTIVE:
            name = self.path.name
            raise ValueError(f"{name} is {self.status}, leaving it alone")
        fields = {"language": language} if language else {}
        self.update(status=Status.queued, redo=redo, **fields)

    def recover(self, min_meeting_s: float) -> bool:
        """Bring a meeting the daemon lost track of (crash, restart) back to the queue, or drop it if short.

        True when the meeting now waits for processing.
        """
        if self.status in LOST:
            for wav in self.path.glob("*.wav"):
                repair_wav(wav)
            self.update(status=Status.queued, stopped_at=self.stopped_at or self.recording_end())
            if self.duration_s < min_meeting_s:
                log.info("discarding short recovered meeting %s", self.path.name)
                shutil.rmtree(self.path)
                return False
        elif self.status == Status.processing:
            self.update(status=Status.queued)
        return self.status == Status.queued

    def recording_end(self) -> str:
        """When the daemon died mid-meeting, the meeting ended where its recording ends."""
        me_wav = self.path / "me.wav"
        if not me_wav.exists():
            return now_iso()
        stopped = self.started_at + timedelta(seconds=recorded_s(me_wav))
        return stopped.isoformat(timespec="seconds")

    def begin(self, default_language: str) -> None:
        """Meetings from before the language setting, and new ones, take the configured language once."""
        language = self.meta.get("language") or default_language
        self.update(status=Status.processing, error=None, stage=None, language=language)

    def enter(self, stage: str) -> None:
        self.update(stage=stage)

    def finish(self) -> None:
        """redo is cleared only now: a worker that dies mid-way retries the same stage."""
        self.update(status=Status.done, stage=None, redo=None)

    def fail(self, message: str) -> None:
        self.update(status=Status.error, stage=None, error=message)

    def worker_died(self, returncode: int) -> None:
        """A worker that died before it could record its own failure."""
        if self.status in UNFINISHED:
            self.fail(f"worker exited with {returncode}")

    def transcript_written(self) -> None:
        self.update(summary_done=False)

    def summary_written(self) -> None:
        self.update(summary_done=True, summary_skipped=False)

    def summary_skipped(self) -> None:
        self.update(summary_skipped=True)

    def outcome(self) -> Outcome | None:
        """None while the meeting is still being recorded or processed."""
        if self.status == Status.error:
            return Outcome.error
        if self.status != Status.done:
            return None
        if self.summary_done:
            return Outcome.summary
        if self.meta.get("summary_skipped"):
            return Outcome.summary_skipped
        return Outcome.transcript_only


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_meta(now: datetime) -> dict[str, Any]:
    return {
        "status": Status.recording,
        "started_at": now.isoformat(timespec="seconds"),
        "stopped_at": None,
        "apps": [],
        "ports": [],
        "gaps": [],
        "warnings": [],
        "summary_done": False,
        "error": None,
        "redo": None,
        "stage": None,
    }


def write_json(path: Path, payload: object) -> None:
    """Write through a temp file, so a reader never sees half a file."""
    staging = path.with_suffix(".tmp")
    staging.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    os.replace(staging, path)


def load_valid(folder: Path) -> Meeting | None:
    try:
        return Meeting.load(folder).checked()
    except OSError, ValueError:
        log.warning("skipping %s: unreadable meta.json", folder)
    return None


def list_meetings(recordings_dir: Path) -> list[Meeting]:
    loaded = (load_valid(meta.parent) for meta in recordings_dir.glob("*/meta.json"))
    return sorted((meeting for meeting in loaded if meeting), key=lambda meeting: meeting.started_at)
