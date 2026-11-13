import array
from datetime import datetime
from pathlib import Path

import pytest

from meetrec.audio import RATE, write_s16
from meetrec.config import Config
from meetrec.engines import Engines
from meetrec.meeting import Meeting, Outcome, Status
from meetrec.process import process

SUMMARY = "# Summary\n"


class FakeEngines:
    """Engines that write fixed tokens and remember what they were asked to do."""

    def __init__(self) -> None:
        self.transcribed: list[str] = []
        self.summaries = 0
        self.summary: str | None = SUMMARY
        self.fail: set[str] = set()

    def engines(self) -> Engines:
        return Engines(transcribe=self.transcribe, clean_me=self.clean_me, summarize=self.summarize)

    def transcribe(self, wav: Path, tsv: Path, language: str) -> None:
        if "transcribe" in self.fail:
            raise RuntimeError("transcription failed")
        self.transcribed.append(wav.name)
        tsv.write_text(f"0\t500\t▁{language}\n")

    def clean_me(self, mic: Path, ref: Path, out: Path) -> None:
        if "echo" in self.fail:
            raise RuntimeError("exit code 1")
        out.write_bytes(mic.read_bytes())

    def summarize(self, transcript: str, language: str, started_at: datetime) -> str | None:
        self.summaries += 1
        if "summary" in self.fail:
            raise RuntimeError("claude returned nothing")
        return self.summary


def recorded(meeting: Meeting, *tracks: str) -> Meeting:
    for track in tracks:
        write_s16(meeting.wav(track), array.array("h", bytes(2 * RATE)))
    meeting.close([])
    return meeting


def run(meeting: Meeting, fake: FakeEngines, echo_cancel: bool = False) -> None:
    cfg = Config(recordings_dir=meeting.path.parent, data_dir=meeting.path.parent, echo_cancel=echo_cancel)
    process(meeting, cfg, fake.engines())


@pytest.mark.parametrize(
    ("redo", "transcribed", "summaries"),
    [("missing", 0, 0), ("transcript", 0, 1), ("all", 2, 1)],
)
def test_redo_runs_only_its_stages(meeting: Meeting, redo: str, transcribed: int, summaries: int) -> None:
    fake = FakeEngines()
    run(recorded(meeting, "me", "them"), fake)
    assert (fake.transcribed, fake.summaries, meeting.outcome()) == (["me.wav", "them.wav"], 1, Outcome.summary)

    meeting.queue(redo)
    run(meeting, fake)

    assert (len(fake.transcribed) - 2, fake.summaries - 1) == (transcribed, summaries)
    assert meeting.status == Status.done


def test_empty_track_is_silence(meeting: Meeting) -> None:
    fake = FakeEngines()

    run(recorded(meeting, "them"), fake)

    assert fake.transcribed == ["them.wav"]
    assert not meeting.tokens("me").read_text()
    assert meeting.meta["warnings"] == ["me.wav is empty, transcribed as silence"]
    assert "**[00:00:00] them:** ru" in meeting.transcript.read_text()


@pytest.mark.parametrize(("fail", "track", "warnings"), [(set(), "me.clean.wav", 0), ({"echo"}, "me.wav", 1)])
def test_echo_falls_back_to_raw_track(meeting: Meeting, fail: set[str], track: str, warnings: int) -> None:
    fake = FakeEngines()
    fake.fail = fail
    recorded(meeting, "me", "them").append("ports", {"sink": "s", "port": "[Out] Speaker"})

    run(meeting, fake, echo_cancel=True)

    assert fake.transcribed[0] == track
    assert len(meeting.meta["warnings"]) == warnings


@pytest.mark.parametrize(
    ("fail", "outcome"), [(set(), Outcome.summary_skipped), ({"summary"}, Outcome.transcript_only)]
)
def test_meeting_is_done_without_summary(meeting: Meeting, fail: set[str], outcome: Outcome) -> None:
    fake = FakeEngines()
    fake.summary = None
    fake.fail = fail

    run(recorded(meeting, "me", "them"), fake)

    assert meeting.outcome() == outcome
    assert not meeting.summary.exists()


def test_failed_transcription_keeps_redo(meeting: Meeting) -> None:
    fake = FakeEngines()
    fake.fail = {"transcribe"}
    recorded(meeting, "me", "them").queue("all")

    with pytest.raises(RuntimeError):
        run(meeting, fake)

    assert (meeting.status, meeting.redo, meeting.error) == (Status.error, "all", "RuntimeError: transcription failed")
