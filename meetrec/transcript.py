from datetime import datetime
from pathlib import Path

Token = tuple[int, int, str]
Phrase = tuple[int, str, str]


def read_tokens(path: Path) -> list[Token]:
    tokens = []
    for line in path.read_text().splitlines():
        t0, t1, piece = line.split("\t")
        tokens.append((int(t0), int(t1), piece))
    return tokens


def write_tokens(path: Path, tokens: list[Token]) -> None:
    path.write_text("".join(f"{t0}\t{t1}\t{piece}\n" for t0, t1, piece in tokens))


def words(tokens: list[Token]) -> list[Token]:
    out: list[list] = []
    for t0, t1, piece in tokens:
        if piece.startswith("▁") or not out:
            out.append([t0, t1, piece.lstrip("▁")])
        else:
            out[-1][1] = t1
            out[-1][2] += piece
    return [(t0, t1, text) for t0, t1, text in out if text]


def phrases(tokens: list[Token], speaker: str, pause_ms: int = 1000, max_ms: int = 15000) -> list[Phrase]:
    ws = words(tokens)
    if not ws:
        return []
    groups, current = [], [ws[0]]
    for prev, word in zip(ws, ws[1:], strict=False):
        too_long = word[0] - current[0][0] >= max_ms and prev[2].endswith((".", "?", "!"))
        if word[0] - prev[1] >= pause_ms or too_long:
            groups.append(current)
            current = []
        current.append(word)
    groups.append(current)
    return [(g[0][0], speaker, " ".join(w[2] for w in g)) for g in groups]


def ts(ms: float) -> str:
    s = int(ms // 1000)
    return f"{s // 3600:02}:{s // 60 % 60:02}:{s % 60:02}"


def render(started: datetime, duration_s: float, *tracks: list[Phrase]) -> str:
    lines = sorted((p for track in tracks for p in track), key=lambda p: p[0])
    head = f"# Встреча {started:%Y-%m-%d %H:%M}\n\nДлительность: {ts(duration_s * 1000)}\n"
    return head + "".join(f"\n**[{ts(t0)}] {speaker}:** {text}\n" for t0, speaker, text in lines)
