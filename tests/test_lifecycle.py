from collections.abc import Sequence

from meetrec.lifecycle import Lifecycle

PAUSE_S = 30
MIN_MEETING_S = 120


def actions(timeline: Sequence[tuple[float, bool]], pause_s: float = PAUSE_S) -> list[str]:
    life = Lifecycle(pause_s, MIN_MEETING_S)
    taken = [life.update(call_on, now) for now, call_on in timeline]
    return [action for action in taken if action]


def test_resume_within_pause_then_close() -> None:
    call = [(0, True), (100, False), (120, True)]
    timeline = [*call, (300, False), (329, False), (330, False)]

    assert actions(timeline) == ["start", "pause", "resume", "pause", "close"]


def test_short_meeting_is_discarded() -> None:
    assert actions([(0, True), (60, False), (90, False)]) == ["start", "pause", "discard"]


def test_pause_is_not_meeting_length() -> None:
    assert actions([(0, True), (100, False), (200, False)], pause_s=100) == ["start", "pause", "discard"]
