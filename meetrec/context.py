"""Past context folder: past meetings and filtered digests of Claude Code sessions, for the summarizer to search."""

import json
import re
import shutil
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from meetrec.meeting import list_meetings

CLAUDE_PROJECTS = Path.home() / ".claude/projects"
STAMP = "%Y-%m-%d %H:%M"
SECRETS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^@\s]+@"),
    re.compile(r"\b(?:sk-[\w-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})"),
    re.compile(r"(?i)\b(?:password|passwd|secret|token|api[_-]?key)\b\s*[:=]\s*\S+"),
    re.compile(r"[\w+/-]{40,}={0,2}"),  # ponytail: crude, eats long hashes too
)


def scrub(text: str) -> str:
    for pattern in SECRETS:
        text = pattern.sub("[secret]", text)
    return text


def rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open() as lines:
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def turn_stamp(row: dict[str, Any]) -> datetime | None:
    """When a person or Claude wrote this row; None for meta rows and everything that is not a turn."""
    if row.get("type") not in {"user", "assistant"} or row.get("isMeta") or "timestamp" not in row:
        return None
    return datetime.fromisoformat(row["timestamp"]).astimezone(UTC)


def turn_lines(row: dict[str, Any]) -> list[str]:
    """Only the text a person or Claude wrote: tool calls, tool output and tagged system text carry secrets."""
    message = row.get("message", {})
    who = "claude" if message.get("role") == "assistant" else "user"
    blocks = message.get("content")
    if isinstance(blocks, str):
        found = [blocks]
    else:
        listed = blocks if isinstance(blocks, list) else []
        found = [block["text"] for block in listed if isinstance(block, dict) and block.get("type") == "text"]
    return [f"**{who}:** {text.strip()}" for text in found if not text.lstrip().startswith("<")]


def header(title: str, turns: list[dict[str, Any]]) -> str:
    places = Counter((turn.get("cwd"), turn.get("gitBranch")) for turn in turns)
    cwd, branch = places.most_common(1)[0][0]
    first = min(turn["at"] for turn in turns).strftime(STAMP)
    last = max(turn["at"] for turn in turns).strftime(STAMP)
    return f"# {title}\n\ncwd: {cwd}, branch: {branch}, {first} – {last} UTC"


def digest(path: Path, since: datetime, until: datetime) -> str | None:
    """A Claude Code session's turns inside [since, until), scrubbed of secrets; None when it has none."""
    title = path.stem
    turns = []
    for row in rows(path):
        title = row.get("aiTitle") or title
        at = turn_stamp(row)
        if at and since <= at < until:
            turns.append({**row, "at": at})
    lines = [line for turn in turns for line in turn_lines(turn)]
    if not lines:
        return None
    return scrub("\n\n".join([header(title, turns), *lines]))


def copy_meetings(folder: Path, recordings_dir: Path, since: datetime, until: datetime) -> None:
    for meeting in list_meetings(recordings_dir):
        if not since <= meeting.started_at < until:
            continue
        for name in ("summary.md", "transcript.md"):
            source = meeting.path / name
            if source.exists():
                target = folder / "meetings" / meeting.path.name / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(source, target)


def write_digests(folder: Path, sessions: Path, since: datetime, until: datetime) -> None:
    for path in sessions.glob("*/*.jsonl"):
        if datetime.fromtimestamp(path.stat().st_mtime, UTC) < since:
            continue
        text = digest(path, since, until)
        if text:
            short_id = path.stem[:8]
            target = folder / "sessions" / f"{short_id}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)


def build_context(folder: Path, recordings_dir: Path, start: datetime, days: int, sessions: Path) -> None:
    """Fill folder with what happened in the days before start; the meeting itself starts at start and stays out."""
    if days <= 0:
        return
    since = start - timedelta(days=days)
    copy_meetings(folder, recordings_dir, since, start)
    write_digests(folder, sessions, since, start)
