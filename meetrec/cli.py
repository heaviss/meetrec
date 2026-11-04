import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from meetrec.config import Config, load_config
from meetrec.daemon import Daemon
from meetrec.install import setup
from meetrec.meeting import ACTIVE, Meeting, list_meetings


def daemon_lines(state: dict[str, Any] | None) -> list[str]:
    if state is None:
        return ["daemon: not running"]
    daemon_state = state["state"]
    meeting = f", {state['meeting']}" if state["meeting"] else ""
    processing = state["processing"] or "—"
    queued = [f"queued: {path}" for path in state["queue"]]
    return [f"daemon: {daemon_state}{meeting}", f"processing: {processing}", *queued]


def attention_line(meeting: Meeting) -> str | None:
    if meeting.status == "error":
        error = meeting.meta["error"]
        return f"error: {meeting.path} — {error}"
    if meeting.status == "done" and not meeting.meta["summary_done"]:
        return f"no summary: {meeting.path}"
    return None


def status(cfg: Config) -> None:
    state = json.loads(cfg.state_path.read_text()) if cfg.state_path.exists() else None
    meetings = list_meetings(cfg.recordings_dir) if cfg.recordings_dir.exists() else []
    attention = [line for line in map(attention_line, meetings) if line]
    sys.stdout.writelines(f"{line}\n" for line in (*daemon_lines(state), *attention))


def redo(folder: Path, stage: str) -> None:
    folder = folder.expanduser().resolve()
    if not (folder / "meta.json").exists():
        sys.exit(f"{folder} is not a meeting folder")
    meeting = Meeting.load(folder)
    if meeting.status in ACTIVE:
        sys.exit(f"{folder.name} is {meeting.status}, leaving it alone")
    meeting.update(status="queued", redo=stage)
    # --kill-whom=main: the default signals the whole cgroup, and SIGUSR1 would kill pw-record.
    subprocess.run(["systemctl", "--user", "kill", "--kill-whom=main", "-s", "USR1", "meetrec"], check=True)
    sys.stdout.write(f"queued {folder.name} ({stage})\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="meetrec")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run", help="the daemon; started by the systemd user unit")
    commands.add_parser("status", help="what the daemon is doing and which meetings need attention")
    commands.add_parser("setup", help="models, LocalVQE, systemd unit; safe to rerun")
    redo_parser = commands.add_parser("redo", help="queue a meeting for processing again")
    redo_parser.add_argument("folder", type=Path)
    stage = redo_parser.add_mutually_exclusive_group()
    rebuild_help = "rebuild transcript.md from *.tokens.tsv, then the summary"
    stage.add_argument("--transcript", action="store_const", const="transcript", dest="stage", help=rebuild_help)
    stage.add_argument("--all", action="store_const", const="all", dest="stage", help="everything, transcription too")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    match args.command:
        case "run":
            Daemon(cfg).run()
        case "status":
            status(cfg)
        case "redo":
            redo(args.folder, args.stage or "missing")
        case "setup":
            setup(cfg)
