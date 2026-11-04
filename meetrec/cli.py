import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from meetrec import config
from meetrec.config import Config
from meetrec.daemon import Daemon
from meetrec.install import setup
from meetrec.meeting import ACTIVE, Meeting, list_meetings


def status(cfg: Config) -> None:
    state = json.loads(cfg.state_path.read_text()) if cfg.state_path.exists() else None
    if not state:
        print("daemon: not running")
    else:
        print(f"daemon: {state['state']}" + (f", {state['meeting']}" if state["meeting"] else ""))
        print(f"processing: {state['processing'] or '—'}")
        for path in state["queue"]:
            print(f"queued: {path}")
    if cfg.recordings_dir.exists():
        for m in list_meetings(cfg.recordings_dir):
            if m.status == "error":
                print(f"error: {m.path} — {m.meta['error']}")
            elif m.status == "done" and not m.meta["summary_done"]:
                print(f"no summary: {m.path}")


def redo(folder: Path, stage: str) -> None:
    folder = folder.expanduser().resolve()
    if not (folder / "meta.json").exists():
        sys.exit(f"{folder} is not a meeting folder")
    meeting = Meeting.load(folder)
    if meeting.status in ACTIVE:
        sys.exit(f"{meeting.path.name} is {meeting.status}, leaving it alone")
    meeting.update(status="queued", redo=stage)
    # --kill-whom=main: the default signals the whole cgroup, and SIGUSR1 would kill pw-record.
    subprocess.run(["systemctl", "--user", "kill", "--kill-whom=main", "-s", "USR1", "meetrec"], check=True)
    print(f"queued {meeting.path.name} ({stage})")


def main() -> None:
    parser = argparse.ArgumentParser(prog="meetrec")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="the daemon; started by the systemd user unit")
    sub.add_parser("status", help="what the daemon is doing and which meetings need attention")
    redo_parser = sub.add_parser("redo", help="queue a meeting for processing again")
    redo_parser.add_argument("folder", type=Path)
    stage = redo_parser.add_mutually_exclusive_group()
    stage.add_argument(
        "--transcript",
        action="store_const",
        const="transcript",
        dest="stage",
        help="rebuild transcript.md from *.tokens.tsv, then the summary",
    )
    stage.add_argument(
        "--all", action="store_const", const="all", dest="stage", help="everything, transcription included"
    )
    sub.add_parser("setup", help="models, LocalVQE, systemd unit; safe to rerun")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = config.load()
    match args.command:
        case "run":
            Daemon(cfg).run()
        case "status":
            status(cfg)
        case "redo":
            redo(args.folder, args.stage or "missing")
        case "setup":
            setup(cfg)
