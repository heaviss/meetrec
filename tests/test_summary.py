from datetime import datetime
from pathlib import Path

import pytest

from meetrec.config import Config
from meetrec.engines import summarize_if_available
from meetrec.summary import summarize, summary_input

TALK = "<transcript>\ntalk\n</transcript>"
START = datetime.fromisoformat("2026-11-13T12:00:00+04:00")


@pytest.fixture(autouse=True)
def no_people(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("meetrec.summary.PEOPLE", tmp_path / "people.md")


def config(tmp_path: Path, *command: str, context_days: int = 0) -> Config:
    return Config(
        user_name="Jane Doe",
        summary_command=command,
        data_dir=tmp_path,
        recordings_dir=tmp_path,
        context_days=context_days,
    )


def test_prompt_file_gets_the_system_prompt(tmp_path: Path) -> None:
    reply = summarize("hello", config(tmp_path, "cat", "{prompt_file}"), "en", START)
    assert "Jane Doe" in reply
    assert "hello" not in reply


def test_system_prompt_leads_stdin(tmp_path: Path) -> None:
    reply = summarize("hello", config(tmp_path, "cat"), "en", START)
    assert reply.index("Jane Doe") < reply.index("<transcript>\nhello\n</transcript>")


def test_empty_reply_fails(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="true returned nothing"):
        summarize("hello", config(tmp_path, "true"), "en", START)


@pytest.mark.parametrize("command", [(), ("no-such-summarizer",)])
def test_missing_summarizer_skips(tmp_path: Path, command: tuple[str, ...]) -> None:
    assert summarize_if_available(config(tmp_path, *command), "hello", "en", START) is None


@pytest.mark.parametrize(
    ("terms", "people", "expected"),
    [
        (
            "terms",
            "Ann",
            "<people>\nAnn\n</people>\n\n<glossary>\nterms\n</glossary>\n\n<transcript>\ntalk\n</transcript>",
        ),
        ("", "", TALK),
    ],
)
def test_blocks_keep_order_and_drop_out(terms: str, people: str, expected: str) -> None:
    assert summary_input("talk", terms, people) == expected


def test_people_lead_stdin(tmp_path: Path) -> None:
    (tmp_path / "people.md").write_text("- Ann Lee")
    reply = summarize("hello", config(tmp_path, "cat", "-", "{prompt_file}"), "en", START)
    assert reply.startswith("<people>\n- Ann Lee\n</people>")


def test_summarizer_runs_in_the_context_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sessions = tmp_path / "sessions" / "p" / "abcdef0123.jsonl"
    sessions.parent.mkdir(parents=True)
    sessions.write_text('{"type": "user", "timestamp": "2026-11-13T07:00:00Z", "message": {"content": "hi"}}')
    monkeypatch.setattr("meetrec.context.CLAUDE_PROJECTS", tmp_path / "sessions")
    assert summarize("hello", config(tmp_path, "ls", "sessions", context_days=1), "en", START) == "abcdef01.md\n"
