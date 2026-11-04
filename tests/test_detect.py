from meetrec.detect import classify, foreign_mic_streams

SOURCES = [
    {"index": 52, "name": "alsa_output.x.monitor", "monitor_of_sink": None},
    {"index": 54, "name": "alsa_input.x", "monitor_of_sink": None},
]


def stream(index, source, **props):
    return {"index": index, "source": source, "properties": props}


def test_foreign_mic_streams_skip_monitor_own_and_denylisted():
    outputs = [
        stream(1, 54, **{"application.name": "Firefox", "application.process.binary": "firefox"}),
        stream(2, 54, **{"application.name": "meetrec"}),
        stream(3, 52, **{"application.name": "meetrec"}),
        stream(4, 52, **{"application.name": "OBS"}),
        stream(5, 54, **{"application.name": "pavucontrol", "application.id": "org.PulseAudio.pavucontrol"}),
    ]

    found = foreign_mic_streams(outputs, SOURCES, ("org.PulseAudio.pavucontrol",))

    assert [s["index"] for s in found] == [1]


def test_classify_keeps_stream_add_remove_and_sink_changes():
    assert classify("Event 'new' on source-output #12") == "mic"
    assert classify("Event 'remove' on source-output #12") == "mic"
    assert classify("Event 'change' on source-output #12") is None
    assert classify("Event 'change' on sink #50") == "sink"
    assert classify("Event 'change' on server #-1") == "sink"
    assert classify("Event 'new' on sink-input #7") is None
