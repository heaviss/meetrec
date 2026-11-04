import json
import logging
import os
import subprocess
from types import MappingProxyType
from typing import Any

log = logging.getLogger(__name__)

# Without LC_ALL=C pactl localizes events, and `pactl -f json` fails on non-ASCII.
C_ENV = MappingProxyType({**os.environ, "LC_ALL": "C"})
# pactl missing, failing, or printing broken JSON (ValueError covers JSONDecodeError).
SNAPSHOT_ERRORS = (OSError, subprocess.SubprocessError, ValueError)
NOT_A_MONITOR = frozenset((None, "", "n/a"))
OWN_APP = "meetrec"

Stream = dict[str, Any]


def pactl_json(*args: str) -> list[Stream]:
    out = subprocess.run(["pactl", "-f", "json", *args], capture_output=True, text=True, check=True, env=C_ENV)
    parsed: list[Stream] = json.loads(out.stdout)
    return parsed


def is_monitor(source: Stream) -> bool:
    return source["name"].endswith(".monitor") or source.get("monitor_of_sink") not in NOT_A_MONITOR


def is_foreign(stream: Stream, monitors: set[int], denylist: tuple[str, ...]) -> bool:
    props = stream["properties"]
    if stream["source"] in monitors or props.get("application.name") == OWN_APP:
        return False
    return props.get("application.id") not in denylist


def foreign_mic_streams(outputs: list[Stream], sources: list[Stream], denylist: tuple[str, ...]) -> list[Stream]:
    monitors = {source["index"] for source in sources if is_monitor(source)}
    return [stream for stream in outputs if is_foreign(stream, monitors, denylist)]


def mic_streams(denylist: tuple[str, ...]) -> list[Stream]:
    return foreign_mic_streams(pactl_json("list", "source-outputs"), pactl_json("list", "sources"), denylist)


def app_of(stream: Stream) -> dict[str, str | None]:
    props = stream["properties"]
    return {"binary": props.get("application.process.binary"), "name": props.get("application.name")}


def default_port() -> dict[str, str | None] | None:
    get_default = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True, env=C_ENV)
    name = get_default.stdout.strip()
    sink = next((sink for sink in pactl_json("list", "sinks") if sink["name"] == name), None)
    if sink is None:
        return None
    return {"sink": name, "port": sink.get("active_port")}
