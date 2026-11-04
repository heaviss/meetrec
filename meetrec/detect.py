import json
import logging
import os
import queue
import re
import subprocess
import time

log = logging.getLogger(__name__)

# Without LC_ALL=C pactl localizes events, and `pactl -f json` fails on non-ASCII.
C_ENV = {**os.environ, "LC_ALL": "C"}
EVENT = re.compile(r"^Event '(new|remove|change)' on (source-output|sink|server)\b")


def pactl_json(*args: str) -> list[dict]:
    out = subprocess.run(["pactl", "-f", "json", *args], capture_output=True, text=True, check=True, env=C_ENV)
    return json.loads(out.stdout)


def foreign_mic_streams(outputs: list[dict], sources: list[dict], denylist: tuple[str, ...]) -> list[dict]:
    monitors = {
        s["index"]
        for s in sources
        if s["name"].endswith(".monitor") or s.get("monitor_of_sink") not in (None, "", "n/a")
    }
    return [
        o
        for o in outputs
        if o["source"] not in monitors
        and o["properties"].get("application.name") != "meetrec"
        and o["properties"].get("application.id") not in denylist
    ]


def mic_streams(denylist: tuple[str, ...]) -> list[dict]:
    return foreign_mic_streams(pactl_json("list", "source-outputs"), pactl_json("list", "sources"), denylist)


def app_of(stream: dict) -> dict:
    props = stream["properties"]
    return {"binary": props.get("application.process.binary"), "name": props.get("application.name")}


def default_port() -> dict | None:
    name = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True, env=C_ENV).stdout.strip()
    sink = next((s for s in pactl_json("list", "sinks") if s["name"] == name), None)
    return {"sink": name, "port": sink.get("active_port")} if sink else None


def classify(line: str) -> str | None:
    if not (m := EVENT.match(line)):
        return None
    action, facility = m.groups()
    if facility == "source-output":
        return "mic" if action != "change" else None
    return "sink" if action == "change" else None


def subscribe(events: queue.Queue) -> None:
    while True:
        with subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, text=True, env=C_ENV) as proc:
            for line in proc.stdout:
                if kind := classify(line.strip()):
                    events.put(kind)
        log.warning("pactl subscribe exited with %s, resubscribing", proc.returncode)
        events.put("mic")
        events.put("sink")
        time.sleep(1)
