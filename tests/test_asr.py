import array

from meetrec.asr import chunks
from meetrec.audio import RATE

LOUD = 1000
TENTH = RATE // 10


def tone(tenths: int, level: int) -> array.array[int]:
    return array.array("h", [level]) * (tenths * TENTH)


def test_chunks_cut_at_quiet_spots_before_limit() -> None:
    quiet = tone(1, 0)
    pieces = (tone(2950, LOUD), quiet, tone(2969, LOUD), quiet, tone(579, LOUD))
    samples = sum(pieces, array.array("h"))
    first_cut, second_cut = 295 * RATE, 592 * RATE

    assert chunks(samples) == [(0, first_cut), (first_cut, second_cut), (second_cut, 650 * RATE)]


def test_short_track_is_one_chunk() -> None:
    assert chunks(tone(10, LOUD)) == [(0, RATE)]
