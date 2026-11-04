import json
import os
import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ACTIVE = frozenset(("recording", "pause", "processing"))
WAV_HEADER = 44
RIFF_SIZE_OFFSET = 4
RIFF_SIZE_EXCLUDES = 8
DATA_TAG_OFFSET = 36
DATA_SIZE_OFFSET = 40
UINT32 = "<I"


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
    def status(self) -> str:
        return str(self.meta["status"])

    @property
    def started_at(self) -> datetime:
        return datetime.fromisoformat(self.meta["started_at"])

    @property
    def duration_s(self) -> float:
        stopped = self.meta["stopped_at"]
        if not stopped:
            return 0
        return (datetime.fromisoformat(stopped) - self.started_at).total_seconds()

    def save(self) -> None:
        staging = self.path / "meta.json.tmp"
        staging.write_text(json.dumps(self.meta, ensure_ascii=False, indent=1))
        os.replace(staging, self.path / "meta.json")

    def update(self, **fields: Any) -> None:
        self.meta.update(fields)
        self.save()

    def append(self, key: str, *entries: Any) -> None:
        self.update(**{key: [*self.meta[key], *entries]})


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_meta(now: datetime) -> dict[str, Any]:
    return {
        "status": "recording",
        "started_at": now.isoformat(timespec="seconds"),
        "stopped_at": None,
        "apps": [],
        "ports": [],
        "gaps": [],
        "warnings": [],
        "summary_done": False,
        "error": None,
        "redo": None,
    }


def list_meetings(recordings_dir: Path) -> list[Meeting]:
    meetings = [Meeting.load(meta.parent) for meta in recordings_dir.glob("*/meta.json")]
    return sorted(meetings, key=lambda meeting: meeting.started_at)


def repair_wav(path: Path) -> bool:
    """Fix RIFF and data sizes that pw-record leaves at zero when killed."""
    size = path.stat().st_size
    if size <= WAV_HEADER:
        return False
    with open(path, "r+b") as wav_file:
        wav_file.seek(DATA_TAG_OFFSET)
        if wav_file.read(4) != b"data":
            return False
        if struct.unpack(UINT32, wav_file.read(4))[0] == size - WAV_HEADER:
            return False
        wav_file.seek(RIFF_SIZE_OFFSET)
        wav_file.write(struct.pack(UINT32, size - RIFF_SIZE_EXCLUDES))
        wav_file.seek(DATA_SIZE_OFFSET)
        wav_file.write(struct.pack(UINT32, size - WAV_HEADER))
    return True
