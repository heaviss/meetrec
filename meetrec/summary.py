import logging
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from types import MappingProxyType

from meetrec import context
from meetrec.config import CONFIG_PATH, PROMPT_FILE, Config

log = logging.getLogger(__name__)

PROMPT = Path(__file__).with_name("prompt.md")
PEOPLE = CONFIG_PATH.with_name("people.md")
LANGUAGE_NAMES = MappingProxyType({"ru": "Russian", "en": "English"})


def glossary_section(repo: Path, name: str) -> str:
    body = (repo / name).read_text()
    return f"### {name}\n{body}"


def glossary(repo: Path | None) -> str:
    if repo is None:
        return ""
    if not (repo / ".git").exists():
        log.warning("no glossary: %s is not a git repository", repo)
        return ""
    listing = subprocess.run(
        ["git", "ls-files", "GLOSSARY-MAP.md", "*GLOSSARY.md"], cwd=repo, capture_output=True, text=True, check=True
    )
    return "\n\n".join(glossary_section(repo, name) for name in listing.stdout.split())


def block(tag: str, body: str) -> str:
    return f"<{tag}>\n{body}\n</{tag}>"


def summary_input(transcript: str, terms: str, people: str = "") -> str:
    parts = [("people", people), ("glossary", terms), ("transcript", transcript)]
    return "\n\n".join(block(tag, body) for tag, body in parts if body or tag == "transcript")


def people_list() -> str:
    return PEOPLE.read_text() if PEOPLE.exists() else ""


def summarizer_available(command: tuple[str, ...]) -> bool:
    return bool(command) and shutil.which(command[0]) is not None


def system_prompt(user_name: str, language: str) -> str:
    return PROMPT.read_text().replace("{user_name}", user_name).replace("{language}", LANGUAGE_NAMES[language])


def summarize(transcript: str, cfg: Config, language: str, started_at: datetime) -> str:
    """Run the summarizer: the system prompt goes to {prompt_file} if the command has one, else ahead of stdin."""
    system = system_prompt(cfg.user_name, language)
    text = summary_input(transcript, glossary(cfg.glossary_repo), people_list())
    if not any(PROMPT_FILE in arg for arg in cfg.summary_command):
        text = f"{system}\n\n{text}"
    with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as prompt_dir:
        context.build_context(Path(folder), cfg.recordings_dir, started_at, cfg.context_days, context.CLAUDE_PROJECTS)
        prompt = Path(prompt_dir) / "prompt.md"
        prompt.write_text(system)
        return run_summarizer(cfg, [arg.replace(PROMPT_FILE, str(prompt)) for arg in cfg.summary_command], text, folder)


def run_summarizer(cfg: Config, command: list[str], text: str, cwd: str) -> str:
    """The context folder is the summarizer's cwd; the prompt sits outside it, so the agent does not read it twice."""
    reply = subprocess.run(
        command,
        input=text,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        timeout=cfg.summary_timeout_s,
    )
    if not reply.stdout.strip():
        stderr = reply.stderr.strip()
        raise RuntimeError(f"{cfg.summary_command[0]} returned nothing: {stderr}")
    return reply.stdout
