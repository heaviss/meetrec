import json
import logging
import os
import queue
import re
import subprocess
import threading
import time
from collections.abc import Callable
from types import MappingProxyType
from typing import Any, NamedTuple

log = logging.getLogger(__name__)

# Without LC_ALL=C pactl localizes events, and `pactl -f json` fails on non-ASCII.
C_ENV = MappingProxyType({**os.environ, "LC_ALL": "C"})
# pactl missing, failing, or printing broken JSON (ValueError covers JSONDecodeError).
SNAPSHOT_ERRORS = (OSError, subprocess.SubprocessError, ValueError)
NOT_A_MONITOR = frozenset((None, "", "n/a"))
OWN_APP = "meetrec"
MIC_EVENT = re.compile(r"^Event '(new|remove)' on source-output #\d+$")
SINK_EVENT = re.compile(r"^Event 'change' on (sink|server) #\S+$")
TICK_S = 1

Stream = dict[str, Any]
Port = dict[str, str | None]
Query = Callable[..., Any]


class Snapshot(NamedTuple):
    """Foreign apps holding the microphone, and the default output's sink and port."""

    streams: list[Stream]
    port: Port | None


def pactl_json(*args: str) -> Any:
    out = subprocess.run(["pactl", "-f", "json", *args], capture_output=True, text=True, check=True, env=C_ENV)
    return json.loads(out.stdout)


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


def app_of(stream: Stream) -> dict[str, str | None]:
    props = stream["properties"]
    return {"binary": props.get("application.process.binary"), "name": props.get("application.name")}


def classify(line: str) -> str | None:
    if MIC_EVENT.match(line):
        return "mic"
    if SINK_EVENT.match(line):
        return "sink"
    return None


class Pactl:
    """What PulseAudio shows, kept current from `pactl subscribe`.

    A failed snapshot keeps the previous one; a crashed subscription resubscribes and snapshots again.
    """

    def __init__(self, denylist: tuple[str, ...], query: Query = pactl_json) -> None:
        self.denylist = denylist
        self.query = query
        self.events: queue.Queue[str] = queue.Queue()
        self.snapshot = Snapshot([], None)

    def start(self, stop: threading.Event) -> None:
        threading.Thread(target=self.subscribe, args=(stop,), daemon=True).start()
        self.snapshot_all()

    def notice(self, line: str) -> None:
        """One line of `pactl subscribe`; microphone and output changes are queued for the next snapshot."""
        kind = classify(line.strip())
        if kind:
            self.events.put(kind)

    def next(self, timeout: float = TICK_S) -> Snapshot:
        """The snapshot after the next event, or the same one after `timeout`, so timers run without events."""
        try:
            event = self.events.get(timeout=timeout)
        except queue.Empty:
            return self.snapshot
        try:
            if event == "mic":
                self.snapshot = self.snapshot._replace(streams=self.mic_streams())
            else:
                self.snapshot = self.snapshot._replace(port=self.default_port())
        except SNAPSHOT_ERRORS:
            log.exception("pactl snapshot failed, keeping the previous one")
        return self.snapshot

    def snapshot_all(self) -> None:
        self.events.put("mic")
        self.events.put("sink")

    def mic_streams(self) -> list[Stream]:
        return foreign_mic_streams(self.query("list", "source-outputs"), self.query("list", "sources"), self.denylist)

    def default_port(self) -> Port | None:
        name = self.query("info").get("default_sink_name")
        sink = next((sink for sink in self.query("list", "sinks") if sink["name"] == name), None)
        if sink is None:
            return None
        return {"sink": name, "port": sink.get("active_port")}

    def subscribe(self, stop: threading.Event) -> None:
        while not stop.is_set():
            try:
                self.watch()
            except OSError, subprocess.SubprocessError, ValueError:
                log.exception("pactl subscribe failed, resubscribing")
            time.sleep(TICK_S)
            # Snapshot again only after the pause: right after a crash pipewire-pulse may still be restarting.
            self.snapshot_all()

    def watch(self) -> None:
        with subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, text=True, env=C_ENV) as proc:
            for line in proc.stdout or ():
                self.notice(line)
            log.warning("pactl subscribe exited with %s, resubscribing", proc.wait())
