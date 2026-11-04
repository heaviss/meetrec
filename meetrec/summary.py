import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import MappingProxyType

from meetrec.config import Config

log = logging.getLogger(__name__)

PROMPT = Path(__file__).with_name("prompt.md")
CLAUDE_TIMEOUT_S = 900
LANGUAGE_NAMES = MappingProxyType({"ru": "Russian", "en": "English"})
CLAUDE = ("claude", "-p", "--no-session-persistence", "--tools", "", "--setting-sources", "project")


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


def claude_input(transcript: str, terms: str) -> str:
    wrapped = f"<transcript>\n{transcript}\n</transcript>"
    if not terms:
        return wrapped
    return f"<glossary>\n{terms}\n</glossary>\n\n{wrapped}"


def claude_available() -> bool:
    return shutil.which(CLAUDE[0]) is not None


def system_prompt(user_name: str, language: str) -> str:
    return PROMPT.read_text().replace("{user_name}", user_name).replace("{language}", LANGUAGE_NAMES[language])


def summarize(transcript: str, cfg: Config, language: str) -> str:
    text = claude_input(transcript, glossary(cfg.glossary_repo))
    with tempfile.TemporaryDirectory() as workdir:
        prompt = Path(workdir) / "prompt.md"
        prompt.write_text(system_prompt(cfg.user_name, language))
        reply = subprocess.run(
            [*CLAUDE, "--system-prompt-file", str(prompt)],
            input=text,
            cwd=workdir,
            capture_output=True,
            text=True,
            check=True,
            timeout=CLAUDE_TIMEOUT_S,
        )
    if not reply.stdout.strip():
        stderr = reply.stderr.strip()
        raise RuntimeError(f"claude returned nothing: {stderr}")
    return reply.stdout
