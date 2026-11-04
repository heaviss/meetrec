from enum import StrEnum


class State(StrEnum):
    idle = "idle"
    recording = "recording"
    pause = "pause"


class Action(StrEnum):
    start = "start"
    pause = "pause"
    resume = "resume"
    close = "close"
    discard = "discard"


class Lifecycle:
    """Idle → recording ⇄ pause → close | discard. Time is passed in, so it can be tested without sleeping."""

    def __init__(self, pause_s: float, min_meeting_s: float) -> None:
        self.pause_s = pause_s
        self.min_meeting_s = min_meeting_s
        self.state = State.idle
        self.started: float = 0
        self.released: float = 0

    def update(self, call_on: bool, now: float) -> Action | None:
        match self.state:
            case State.idle if call_on:
                self.state = State.recording
                self.started = now
                return Action.start
            case State.recording if not call_on:
                self.state = State.pause
                self.released = now
                return Action.pause
            case State.pause if call_on:
                self.state = State.recording
                return Action.resume
            case State.pause if now - self.released >= self.pause_s:
                self.state = State.idle
                long_enough = self.released - self.started >= self.min_meeting_s
                return Action.close if long_enough else Action.discard
        return None

    def meeting_length(self, now: float) -> float:
        if self.state == State.recording:
            return now - self.started
        if self.state == State.pause:
            return self.released - self.started
        return 0
