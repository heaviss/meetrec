from meetrec.daemon import Lifecycle


def run(timeline, pause_s=30, min_meeting_s=120):
    life = Lifecycle(pause_s, min_meeting_s)
    return [action for now, call_on in timeline if (action := life.update(call_on, now))]


def test_meeting_resumes_within_pause_and_closes_after_it():
    actions = run([(0, True), (100, False), (120, True), (300, False), (329, False), (330, False)])

    assert actions == ["start", "pause", "resume", "pause", "close"]


def test_short_meeting_is_discarded():
    assert run([(0, True), (60, False), (90, False)]) == ["start", "pause", "discard"]


def test_pause_does_not_count_towards_meeting_length():
    assert run([(0, True), (100, False), (200, False)], pause_s=100) == ["start", "pause", "discard"]
