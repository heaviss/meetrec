from datetime import datetime
from pathlib import Path

import pytest

from meetrec.meeting import Meeting

STARTED = datetime.fromisoformat("2026-11-04T09:00:00+04:00")


@pytest.fixture
def meeting(tmp_path: Path) -> Meeting:
    return Meeting.create(tmp_path, STARTED)
