import shutil
from datetime import datetime
from pathlib import Path

import pytest

from meetrec.cli import attention_line
from meetrec.config import Config
from meetrec.meeting import Meeting
from meetrec.process import write_summary


def test_summary_is_skipped_without_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    meeting = Meeting.create(tmp_path, datetime(2026, 11, 2, 17, 30))
    meeting.update(status="done")

    write_summary(meeting, Config())

    assert meeting.meta["summary_skipped"]
    assert not (meeting.path / "summary.md").exists()
    assert attention_line(meeting) is None
