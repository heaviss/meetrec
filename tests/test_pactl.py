from typing import Any

import pytest

from meetrec.pactl import Pactl, Stream, classify, foreign_mic_streams

MONITOR = 52
MIC = 54
SOURCES = (
    {"index": MONITOR, "name": "alsa_output.x.monitor", "monitor_of_sink": None},
    {"index": MIC, "name": "alsa_input.x", "monitor_of_sink": None},
)
DENYLIST = ("org.PulseAudio.pavucontrol",)
NEW_MIC = "Event 'new' on source-output #12\n"


def stream(index: int, source: int, props: dict[str, str]) -> Stream:
    return {"index": index, "source": source, "properties": props}


class FakePactl:
    """Answers `pactl -f json` queries from a table, or fails while `broken`."""

    def __init__(self) -> None:
        self.broken = False
        self.asked: list[tuple[str, ...]] = []
        self.answers: dict[tuple[str, ...], Any] = {
            ("list", "source-outputs"): [stream(1, MIC, {"application.process.binary": "firefox"})],
            ("list", "sources"): list(SOURCES),
            ("info",): {"default_sink_name": "speakers"},
            ("list", "sinks"): [{"name": "speakers", "active_port": "[Out] Speaker"}],
        }

    def __call__(self, *args: str) -> Any:
        self.asked.append(args)
        if self.broken:
            raise OSError("pactl is gone")
        return self.answers[args]


def test_only_foreign_mic_streams_count() -> None:
    outputs = [
        stream(1, MIC, {"application.name": "Firefox", "application.process.binary": "firefox"}),
        stream(2, MIC, {"application.name": "meetrec"}),
        stream(3, MONITOR, {"application.name": "meetrec"}),
        stream(4, MONITOR, {"application.name": "OBS"}),
        stream(5, MIC, {"application.name": "pavucontrol", "application.id": "org.PulseAudio.pavucontrol"}),
    ]

    found = foreign_mic_streams(outputs, list(SOURCES), DENYLIST)

    assert [found_stream["index"] for found_stream in found] == [1]


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("Event 'new' on source-output #12", "mic"),
        ("Event 'remove' on source-output #12", "mic"),
        ("Event 'change' on source-output #12", None),
        ("Event 'change' on sink #50", "sink"),
        ("Event 'change' on server #-1", "sink"),
        ("Event 'new' on sink-input #7", None),
        ("Event 'change' on sink-input #7", None),
    ],
)
def test_classify(line: str, kind: str | None) -> None:
    assert classify(line) == kind


def test_mic_event_refreshes_only_streams() -> None:
    fake = FakePactl()
    pactl = Pactl(DENYLIST, query=fake)

    pactl.notice(NEW_MIC)
    streams, port = pactl.next(timeout=0)

    assert [found["index"] for found in streams] == [1]
    assert port is None
    assert fake.asked == [("list", "source-outputs"), ("list", "sources")]


def test_sink_event_reads_default_port() -> None:
    pactl = Pactl(DENYLIST, query=FakePactl())

    pactl.notice("Event 'change' on server #-1\n")

    assert pactl.next(timeout=0).port == {"sink": "speakers", "port": "[Out] Speaker"}


def test_tick_asks_nothing() -> None:
    fake = FakePactl()

    Pactl(DENYLIST, query=fake).next(timeout=0)

    assert fake.asked == []


def test_failed_snapshot_keeps_previous() -> None:
    fake = FakePactl()
    pactl = Pactl(DENYLIST, query=fake)
    pactl.notice(NEW_MIC)
    seen = pactl.next(timeout=0)
    fake.broken = True

    pactl.notice(NEW_MIC)

    assert pactl.next(timeout=0) == seen
