"""PROTOTYPE, throwaway (ticket 03): who picks summary context, the agent or meetrec.

For each meeting dir it builds one context folder (past meetings' summary.md + transcript.md
and a filtered digest of Claude Code sessions, WINDOW days back from the meeting start) and runs
three summaries with `--output-format json`:

  none     today's behaviour: glossary + transcript, no tools
  meetrec  meetrec picks the context (IDF word overlap with the transcript, under BUDGET chars) into stdin
  agent    tools Read,Grep,Glob, cwd = the context folder, the agent searches it itself

Outputs (real speech, kept out of the repo) go to OUT/<meeting>/. Prints a cost/time table.

    uv run python .scratch/summary-context/checks/context_source.py OUT ~/Recordings/2026-11-12-1400 ...
"""

import json
import math
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from meetrec.config import PROMPT_FILE, load_config
from meetrec.summary import glossary, summary_input, system_prompt

WINDOW = timedelta(days=14)
BUDGET = 60_000  # chars of context meetrec puts into stdin
SESSIONS = Path.home() / ".claude" / "projects"

SECRETS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^@\s]+@"),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})"),
    re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\b\s*[:=]\s*\S+"),
    re.compile(r"\b[A-Za-z0-9+/_-]{40,}={0,2}"),  # ponytail: crude, eats long hashes too
]

CONTEXT_NOTE = {
    "meetrec": (
        "\n\nThe input may also have a <context> block: summaries and transcripts of the user's past meetings "
        "and digests of their recent Claude Code sessions. Use it only to restore garbled terms, names and ticket "
        "numbers, and to link tasks to earlier work. Do not summarize the context itself."
    ),
    "agent": (
        "\n\nYour working directory holds context: `meetings/<date>/summary.md` and `transcript.md` of the user's "
        "past meetings and `sessions/*.md`, digests of their recent Claude Code sessions. Search it with Grep, Glob "
        "and Read to restore garbled terms, names and ticket numbers and to link tasks to earlier work. "
        "Do not summarize the context itself."
    ),
}


def scrub(text: str) -> str:
    for pattern in SECRETS:
        text = pattern.sub("[secret]", text)
    return text


def texts(content: object) -> list[str]:
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return []


def digest(path: Path, since: datetime, until: datetime) -> str | None:
    title, cwds, turns, stamps = "", Counter(), [], []
    for line in path.open():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("type") == "ai-title":
            title = row.get("aiTitle") or row.get("title") or title
        if row.get("type") not in {"user", "assistant"} or row.get("isMeta"):
            continue
        at = datetime.fromisoformat(row["timestamp"])
        if not since <= at <= until:
            continue
        stamps.append(at)
        cwds[(row.get("cwd"), row.get("gitBranch"))] += 1
        for text in texts(row.get("message", {}).get("content")):
            if text.lstrip().startswith("<"):  # system reminders, command tags
                continue
            who = "user" if row["type"] == "user" else "claude"
            turns.append(f"**{who}:** {text.strip()}")
    if not turns:
        return None
    (cwd, branch), _ = cwds.most_common(1)[0]
    head = f"# {title or path.stem}\n\ncwd: {cwd}, branch: {branch}, {min(stamps):%Y-%m-%d %H:%M} – {max(stamps):%H:%M} UTC\n\n"
    return scrub(head + "\n\n".join(turns))


def build_context(meeting: Path, ctx: Path) -> None:
    start = datetime.fromisoformat(json.loads((meeting / "meta.json").read_text())["started_at"])
    since = start - WINDOW
    for past in sorted(meeting.parent.iterdir()):
        meta = past / "meta.json"
        if past == meeting or not meta.exists():
            continue
        if not since <= datetime.fromisoformat(json.loads(meta.read_text())["started_at"]) < start:
            continue
        for name in ("summary.md", "transcript.md"):
            if (past / name).exists():
                (ctx / "meetings" / past.name).mkdir(parents=True, exist_ok=True)
                shutil.copy(past / name, ctx / "meetings" / past.name / name)
    (ctx / "sessions").mkdir(parents=True, exist_ok=True)
    for path in SESSIONS.glob("*/*.jsonl"):
        if datetime.fromtimestamp(path.stat().st_mtime, UTC) < since:
            continue
        text = digest(path, since, start)
        if text:
            (ctx / "sessions" / f"{path.stem[:8]}.md").write_text(text)


WORD = re.compile(r"\w{5,}|[A-Z]+-\d+")


def words(text: str) -> set[str]:
    return {w.lower() for w in WORD.findall(text)}


def pick(transcript: str, ctx: Path) -> str:
    """Deterministic: past summaries and session digests ranked by IDF-weighted word overlap, under BUDGET."""
    docs = {p: p.read_text() for p in [*ctx.glob("meetings/*/summary.md"), *ctx.glob("sessions/*.md")]}
    bags = {p: words(t) for p, t in docs.items()}
    df = Counter(w for bag in bags.values() for w in bag)
    want = words(transcript)
    score = {p: sum(math.log(len(docs) / df[w]) for w in bag & want) / math.sqrt(len(bag) + 1) for p, bag in bags.items()}
    out, used = [], 0
    for p in sorted(docs, key=score.get, reverse=True):
        if score[p] <= 0 or used + len(docs[p]) > BUDGET:
            continue
        out.append(f"### {p.relative_to(ctx)}\n{docs[p]}")
        used += len(docs[p])
    return "\n\n".join(out)


def run(variant: str, meeting: Path, ctx: Path, out: Path) -> dict:
    cfg = load_config()
    lang = json.loads((meeting / "meta.json").read_text())["language"]
    transcript = (meeting / "transcript.md").read_text()
    system = system_prompt(cfg.user_name, lang) + CONTEXT_NOTE.get(variant, "")
    text = summary_input(transcript, glossary(cfg.glossary_repo))
    command = list(cfg.summary_command)
    cwd = out
    if variant == "meetrec":
        picked = pick(transcript, ctx)
        (out / "meetrec-context.md").write_text(picked)
        text = f"<context>\n{picked}\n</context>\n\n{text}"
    if variant == "agent":
        command[command.index("--tools") + 1] = "Read,Grep,Glob"
        command += ["--permission-mode", "dontAsk"]
        cwd = ctx
    prompt = out / f"{variant}-prompt.md"
    prompt.write_text(system)
    command = [a.replace(PROMPT_FILE, str(prompt)) for a in command] + ["--output-format", "json"]
    began = time.monotonic()
    reply = subprocess.run(command, input=text, cwd=cwd, capture_output=True, text=True, check=True)
    took = time.monotonic() - began
    result = json.loads(reply.stdout)
    (out / f"{variant}.md").write_text(result["result"])
    u = result["usage"]
    return {
        "meeting": meeting.name,
        "variant": variant,
        "s": round(took),
        "usd": round(result["total_cost_usd"], 3),
        "turns": result.get("num_turns"),
        "in": u["input_tokens"] + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
        "out": u["output_tokens"],
        "stdin_chars": len(text),
    }


def main(out_root: Path, meetings: list[Path]) -> None:
    jobs = []
    for meeting in meetings:
        out = out_root / meeting.name
        ctx = out / "ctx"
        shutil.rmtree(ctx, ignore_errors=True)
        ctx.mkdir(parents=True)
        build_context(meeting, ctx)
        jobs += [(v, meeting, ctx, out) for v in ("none", "meetrec", "agent")]
    with ThreadPoolExecutor(6) as pool:
        rows = list(pool.map(lambda job: run(*job), jobs))
    (out_root / "stats.json").write_text(json.dumps(rows, indent=1))
    for row in rows:
        print("\t".join(str(v) for v in row.values()))


if __name__ == "__main__":
    main(Path(sys.argv[1]), [Path(a) for a in sys.argv[2:]])
