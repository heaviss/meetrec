import json
import os
import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ACTIVE = {"recording", "pause", "processing"}
WAV_HEADER = 44


@dataclass
class Meeting:
    path: Path
    meta: dict

    @classmethod
    def create(cls, recordings_dir: Path, now: datetime) -> Meeting:
        base = recordings_dir / now.strftime("%Y-%m-%d-%H%M")
        path, n = base, 1
        while path.exists():
            n += 1
            path = base.with_name(f"{base.name}-{n}")
        path.mkdir(parents=True)
        meeting = cls(
            path,
            {
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
            },
        )
        meeting.save()
        return meeting

    @classmethod
    def load(cls, path: Path) -> Meeting:
        path = Path(path)
        return cls(path, json.loads((path / "meta.json").read_text()))

    def save(self) -> None:
        tmp = self.path / "meta.json.tmp"
        tmp.write_text(json.dumps(self.meta, ensure_ascii=False, indent=1))
        os.replace(tmp, self.path / "meta.json")

    def update(self, **fields) -> None:
        self.meta.update(fields)
        self.save()

    @property
    def status(self) -> str:
        return self.meta["status"]

    @property
    def started_at(self) -> datetime:
        return datetime.fromisoformat(self.meta["started_at"])

    @property
    def duration_s(self) -> float:
        stopped = self.meta["stopped_at"]
        return (datetime.fromisoformat(stopped) - self.started_at).total_seconds() if stopped else 0


def list_meetings(recordings_dir: Path) -> list[Meeting]:
    meetings = [Meeting.load(meta.parent) for meta in recordings_dir.glob("*/meta.json")]
    return sorted(meetings, key=lambda m: m.started_at)


def repair_wav(path: Path) -> bool:
    """Fix RIFF and data sizes that pw-record leaves at zero when killed."""
    size = path.stat().st_size
    if size <= WAV_HEADER:
        return False
    with open(path, "r+b") as f:
        f.seek(36)
        if f.read(4) != b"data":
            return False
        if struct.unpack("<I", f.read(4))[0] == size - WAV_HEADER:
            return False
        f.seek(4)
        f.write(struct.pack("<I", size - 8))
        f.seek(40)
        f.write(struct.pack("<I", size - WAV_HEADER))
    return True
