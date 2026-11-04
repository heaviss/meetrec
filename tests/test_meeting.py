import pytest

from meetrec.meeting import Meeting, Outcome, Status


def test_close_keeps_release_moment(meeting: Meeting) -> None:
    meeting.pause()
    released = meeting.stopped_at

    meeting.close([])

    assert Meeting.load(meeting.path).status == Status.queued
    assert meeting.stopped_at == released


def test_active_meeting_is_not_requeued(meeting: Meeting) -> None:
    with pytest.raises(ValueError, match="leaving it alone"):
        meeting.queue("all")


def test_queue_sets_language(meeting: Meeting) -> None:
    meeting.update(status=Status.done)

    meeting.queue("all", "en")

    assert (meeting.status, meeting.redo, meeting.meta["language"]) == (Status.queued, "all", "en")


def test_worker_death_marks_only_unfinished_work(meeting: Meeting) -> None:
    meeting.begin("ru")
    meeting.finish()

    meeting.worker_died(1)
    assert meeting.status == Status.done

    meeting.queue("all")
    meeting.worker_died(1)
    assert meeting.error == "worker exited with 1"


def test_failure_keeps_redo_for_retry(meeting: Meeting) -> None:
    meeting.update(status=Status.done)
    meeting.queue("transcript")
    meeting.begin("ru")
    meeting.enter("summary")

    meeting.fail("boom")

    assert (meeting.outcome(), meeting.redo, meeting.stage) == (Outcome.error, "transcript", None)


def test_outcome_follows_summary(meeting: Meeting) -> None:
    assert meeting.outcome() is None

    meeting.begin("ru")
    meeting.transcript_written()
    meeting.finish()
    assert meeting.outcome() == Outcome.transcript_only

    meeting.summary_skipped()
    assert meeting.outcome() == Outcome.summary_skipped

    meeting.summary_written()
    assert meeting.outcome() == Outcome.summary
