import logging
import queue
import re
import subprocess
import threading
import time

from meetrec.detect import C_ENV

log = logging.getLogger(__name__)

MIC_EVENT = re.compile(r"^Event '(new|remove)' on source-output #\d+$")
SINK_EVENT = re.compile(r"^Event 'change' on (sink|server) #\S+$")


def event_queue() -> queue.Queue[str]:
    return queue.Queue()


def next_event(events: queue.Queue[str]) -> str:
    """The next pactl event, or a tick once a second so timers run without events."""
    try:
        return events.get(timeout=1)
    except queue.Empty:
        return "tick"


def classify(line: str) -> str | None:
    if MIC_EVENT.match(line):
        return "mic"
    if SINK_EVENT.match(line):
        return "sink"
    return None


def watch(events: queue.Queue[str]) -> None:
    with subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, text=True, env=C_ENV) as proc:
        for line in proc.stdout or ():
            kind = classify(line.strip())
            if kind:
                events.put(kind)
        log.warning("pactl subscribe exited with %s, resubscribing", proc.wait())


def subscribe(events: queue.Queue[str], stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            watch(events)
        except OSError, subprocess.SubprocessError, ValueError:
            log.exception("pactl subscribe failed, resubscribing")
        time.sleep(1)
        # Snapshot again only after the pause: right after a crash pipewire-pulse may still be restarting.
        events.put("mic")
        events.put("sink")
