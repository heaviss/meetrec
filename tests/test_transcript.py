from datetime import datetime

from meetrec.transcript import phrases, render


def test_tokens_glue_into_words_and_split_on_pause():
    tokens = [(0, 40, "▁При"), (40, 80, "вет"), (80, 120, "."), (2000, 2040, "▁Как"), (2100, 2140, "▁дела")]

    assert phrases(tokens, "me") == [(0, "me", "Привет."), (2000, "me", "Как дела")]


def test_long_phrase_splits_only_at_sentence_end():
    tokens = [(i * 500, i * 500 + 40, f"▁w{i}" + ("." if i == 33 else "")) for i in range(40)]

    starts = [t0 for t0, _, _ in phrases(tokens, "them")]

    assert starts == [0, 17000]


def test_render_interleaves_tracks_by_start():
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
