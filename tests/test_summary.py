from pathlib import Path

import pytest

from meetrec.config import Config
from meetrec.engines import summarize_if_available
from meetrec.summary import summarize


def config(tmp_path: Path, *command: str) -> Config:
    return Config(user_name="Jane Doe", summary_command=command, data_dir=tmp_path)


def test_prompt_file_gets_the_system_prompt(tmp_path: Path) -> None:
    reply = summarize("hello", config(tmp_path, "cat", "{prompt_file}"), "en")
    assert "Jane Doe" in reply
    assert "hello" not in reply


def test_system_prompt_leads_stdin(tmp_path: Path) -> None:
    reply = summarize("hello", config(tmp_path, "cat"), "en")
    assert reply.index("Jane Doe") < reply.index("<transcript>\nhello\n</transcript>")


def test_empty_reply_fails(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="true returned nothing"):
        summarize("hello", config(tmp_path, "true"), "en")


@pytest.mark.parametrize("command", [(), ("no-such-summarizer",)])
def test_missing_summarizer_skips(tmp_path: Path, command: tuple[str, ...]) -> None:
    assert summarize_if_available(config(tmp_path, *command), "hello", "en") is None
