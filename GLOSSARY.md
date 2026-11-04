# meetrec

Local recording and transcription of the user's calls.

## Language

**Meeting**:
One call recorded from the moment another app takes the microphone until it lets go of it for longer than the grace period.
_Avoid_: session, recording, call

**Track `me`**:
The user's microphone during a meeting.
_Avoid_: mic track, local track

**Track `them`**:
Everything the computer played during a meeting: the other participants, plus any other system sound.
_Avoid_: system track, remote track, loopback

**Echo**:
The other participants' voices picked up by the microphone from the speakers, so they appear in track `me` too.
_Avoid_: bleed, crosstalk

**Clean `me`**:
A copy of track `me` with the echo removed, using track `them` as the reference; the original track `me` is kept.
_Avoid_: denoised track, filtered mic

**Transcript**:
The text of a meeting, with each line marked as `me` or `them` and timestamped.

**Summary**:
A short write-up of a meeting made from its transcript.
