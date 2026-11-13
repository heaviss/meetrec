import json
from datetime import datetime, timedelta
from pathlib import Path

from meetrec.context import build_context, scrub
from meetrec.meeting import new_meta

START = datetime.fromisoformat("2026-11-13T12:00:00+04:00")


def meeting(recordings: Path, name: str, started: datetime) -> None:
    folder = recordings / name
    folder.mkdir(parents=True)
    (folder / "meta.json").write_text(json.dumps(new_meta(started)))
    (folder / "summary.md").write_text(f"summary of {name}")


def session(sessions: Path, *rows: dict[str, object]) -> None:
    path = sessions / "project" / "abcdef0123456789.jsonl"
    path.parent.mkdir(parents=True)
    lines = [*map(json.dumps, rows), "not json"]
    path.write_text("\n".join(lines))


def turn(kind: str, at: datetime, blocks: object, **extra: object) -> dict[str, object]:
    stamp = at.astimezone().isoformat()
    return {"type": kind, "timestamp": stamp, "cwd": "/src/app", "message": {"role": kind, "content": blocks}, **extra}


def test_window_ends_at_the_meeting(tmp_path: Path) -> None:
    recordings, sessions, folder = tmp_path / "rec", tmp_path / "sessions", tmp_path / "ctx"
    meeting(recordings, "old", START - timedelta(days=15))
    meeting(recordings, "recent", START - timedelta(days=1))
    meeting(recordings, "this", START)
    session(
        sessions,
        turn("user", START - timedelta(days=20), "too old"),
        turn("user", START - timedelta(hours=2), "fix PROJ-12"),
        turn("user", START + timedelta(hours=1), "after the meeting"),
    )
    build_context(folder, recordings, START, 14, sessions)
    assert sorted(path.name for path in (folder / "meetings").iterdir()) == ["recent"]
    digest = (folder / "sessions/abcdef01.md").read_text()
    assert "fix PROJ-12" in digest
    assert "too old" not in digest
    assert "after the meeting" not in digest


def test_digest_keeps_only_written_text(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions"
    at = START - timedelta(hours=1)
    tool_call = [{"type": "tool_use", "input": {"command": "cat .env"}}, {"type": "text", "text": "reading"}]
    session(
        sessions,
        turn("user", at, "<system-reminder>hidden</system-reminder>"),
        turn("user", at, "meta text", isMeta=True),
        turn("assistant", at, tool_call),
        turn("user", at, [{"type": "tool_result", "content": "DB_PASS=hunter2"}]),
        {"type": "ai-title", "aiTitle": "Payments refactor"},
    )
    build_context(tmp_path / "ctx", tmp_path / "rec", START, 14, sessions)
    digest = (tmp_path / "ctx/sessions/abcdef01.md").read_text()
    assert digest.startswith("# Payments refactor\n\ncwd: /src/app")
    assert "**claude:** reading" in digest
    for leaked in ("hidden", "meta text", "cat .env", "hunter2"):
        assert leaked not in digest


def test_scrub_masks_secrets() -> None:
    text = "key sk-abcdefghijklmnopqrstuv, db postgres://app:pw@host/db, token: abc123, ok"
    assert scrub(text) == "key [secret], db [secret]host/db, [secret] ok"


def test_zero_days_leaves_the_folder_empty(tmp_path: Path) -> None:
    folder = tmp_path / "ctx"
    folder.mkdir()
    meeting(tmp_path / "rec", "recent", START - timedelta(days=1))
    build_context(folder, tmp_path / "rec", START, 0, tmp_path)
    assert not list(folder.iterdir())
