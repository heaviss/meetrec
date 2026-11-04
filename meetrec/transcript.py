from datetime import datetime
from pathlib import Path

Token = tuple[int, int, str]
Phrase = tuple[int, str, str]

PAUSE_MS = 1000
MAX_PHRASE_MS = 15000
MS_PER_S = 1000
SECONDS_PER_MINUTE = 60
SENTENCE_END = (".", "?", "!")
# GigaAM marks a word start with the SentencePiece "▁", Parakeet with a plain space.
WORD_STARTS = ("▁", " ")


def read_tokens(path: Path) -> list[Token]:
    tokens = []
    for row in path.read_text().splitlines():
        start_ms, end_ms, piece = row.split("\t")
        tokens.append((int(start_ms), int(end_ms), piece))
    return tokens


def write_tokens(path: Path, tokens: list[Token]) -> None:
    rows = ("\t".join(map(str, token)) for token in tokens)
    path.write_text("".join(f"{row}\n" for row in rows))


def glue(glued: list[Token], token: Token) -> None:
    start_ms, end_ms, piece = token
    if piece.startswith(WORD_STARTS) or not glued:
        glued.append((start_ms, end_ms, piece.lstrip("".join(WORD_STARTS))))
        return
    word_start, _, text = glued[-1]
    glued[-1] = (word_start, end_ms, f"{text}{piece}")


def words(tokens: list[Token]) -> list[Token]:
    glued: list[Token] = []
    for token in tokens:
        glue(glued, token)
    return [word for word in glued if word[2]]


def breaks_phrase(phrase_start: int, prev: Token, word: Token) -> bool:
    too_long = word[0] - phrase_start >= MAX_PHRASE_MS and prev[2].endswith(SENTENCE_END)
    return word[0] - prev[1] >= PAUSE_MS or too_long


def phrases(tokens: list[Token], speaker: str) -> list[Phrase]:
    all_words = words(tokens)
    groups: list[list[Token]] = []
    for index, word in enumerate(all_words):
        if not index or breaks_phrase(groups[-1][0][0], all_words[index - 1], word):
            groups.append([])
        groups[-1].append(word)
    return [(group[0][0], speaker, " ".join(member[2] for member in group)) for group in groups]


def clock(ms: float) -> str:
    minutes, seconds = divmod(int(ms // MS_PER_S), SECONDS_PER_MINUTE)
    hours, minutes = divmod(minutes, SECONDS_PER_MINUTE)
    return ":".join(str(part).zfill(2) for part in (hours, minutes, seconds))


def line(phrase: Phrase) -> str:
    start, speaker, text = phrase
    stamp = clock(start)
    label = f"[{stamp}] {speaker}:"
    return f"\n**{label}** {text}\n"


def render(started: datetime, duration_s: float, *tracks: list[Phrase]) -> str:
    ordered = sorted((phrase for track in tracks for phrase in track), key=lambda phrase: phrase[0])
    title = started.strftime("%Y-%m-%d %H:%M")
    duration = clock(duration_s * MS_PER_S)
    header = f"# Встреча {title}\n\nДлительность: {duration}\n"
    return "".join((header, *map(line, ordered)))
