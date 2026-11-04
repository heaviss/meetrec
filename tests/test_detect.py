import pytest

from meetrec.detect import Stream, classify, foreign_mic_streams

MONITOR = 52
MIC = 54
SOURCES = (
    {"index": MONITOR, "name": "alsa_output.x.monitor", "monitor_of_sink": None},
    {"index": MIC, "name": "alsa_input.x", "monitor_of_sink": None},
)


def stream(index: int, source: int, props: dict[str, str]) -> Stream:
    return {"index": index, "source": source, "properties": props}


def test_only_foreign_mic_streams_count() -> None:
    outputs = [
        stream(1, MIC, {"application.name": "Firefox", "application.process.binary": "firefox"}),
        stream(2, MIC, {"application.name": "meetrec"}),
        stream(3, MONITOR, {"application.name": "meetrec"}),
        stream(4, MONITOR, {"application.name": "OBS"}),
        stream(5, MIC, {"application.name": "pavucontrol", "application.id": "org.PulseAudio.pavucontrol"}),
    ]

    found = foreign_mic_streams(outputs, list(SOURCES), ("org.PulseAudio.pavucontrol",))

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
    ],
)
def test_classify(line: str, kind: str | None) -> None:
    assert classify(line) == kind
