from datetime import datetime

from meetrec.transcript import Token, phrases, render

STEP_MS = 500
SENTENCE_END_WORD = 33


def word_token(index: int) -> Token:
    dot = "." if index == SENTENCE_END_WORD else ""
    start = index * STEP_MS
    return (start, start + 40, f"▁w{index}{dot}")


def test_tokens_glue_into_words_split_on_pause() -> None:
    hello = [(0, 40, "▁При"), (40, 80, "вет"), (80, 120, ".")]
    tokens = [*hello, (2000, 2040, "▁Как"), (2100, 2140, "▁дела")]

    assert phrases(tokens, "me") == [(0, "me", "Привет."), (2000, "me", "Как дела")]


def test_parakeet_tokens_start_words_with_a_space() -> None:
    so = [(240, 560, " And"), (560, 800, " so"), (800, 960, ",")]
    tokens = [*so, (2280, 2360, " fe"), (2360, 2520, "llow")]

    assert phrases(tokens, "me") == [(240, "me", "And so,"), (2280, "me", "fellow")]


def test_long_phrase_splits_at_sentence_end() -> None:
    tokens = [word_token(index) for index in range(40)]

    starts = [phrase[0] for phrase in phrases(tokens, "them")]

    assert starts == [0, 17000]


def test_render_interleaves_tracks_by_start() -> None:
    me = [(1000, "me", "Да."), (9000, "me", "Согласен.")]
    them = [(0, "them", "Начнём?"), (5000, "them", "Есть вопрос.")]

    text = render(datetime(2026, 11, 2, 17, 30), 3725, me, them)

    assert text == (
        "# Встреча 2026-11-02 17:30\n\nДлительность: 01:02:05\n"
        "\n**[00:00:00] them:** Начнём?\n"
        "\n**[00:00:01] me:** Да.\n"
        "\n**[00:00:05] them:** Есть вопрос.\n"
        "\n**[00:00:09] me:** Согласен.\n"
    )
