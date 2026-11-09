import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import MappingProxyType

from meetrec.config import PROMPT_FILE, Config

log = logging.getLogger(__name__)

PROMPT = Path(__file__).with_name("prompt.md")
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


def summary_input(transcript: str, terms: str) -> str:
    wrapped = f"<transcript>\n{transcript}\n</transcript>"
    if not terms:
        return wrapped
    return f"<glossary>\n{terms}\n</glossary>\n\n{wrapped}"


def summarizer_available(command: tuple[str, ...]) -> bool:
    return bool(command) and shutil.which(command[0]) is not None


def system_prompt(user_name: str, language: str) -> str:
    return PROMPT.read_text().replace("{user_name}", user_name).replace("{language}", LANGUAGE_NAMES[language])


def summarize(transcript: str, cfg: Config, language: str) -> str:
    """Run the summarizer: the system prompt goes to {prompt_file} if the command has one, else ahead of stdin."""
    system = system_prompt(cfg.user_name, language)
    text = summary_input(transcript, glossary(cfg.glossary_repo))
    if not any(PROMPT_FILE in arg for arg in cfg.summary_command):
        text = f"{system}\n\n{text}"
    return run_summarizer(cfg, system, text)


def run_summarizer(cfg: Config, system: str, text: str) -> str:
    with tempfile.TemporaryDirectory() as workdir:
        prompt = Path(workdir) / "prompt.md"
        prompt.write_text(system)
        reply = subprocess.run(
            [arg.replace(PROMPT_FILE, str(prompt)) for arg in cfg.summary_command],
            input=text,
            cwd=workdir,
            capture_output=True,
            text=True,
            check=True,
            timeout=cfg.summary_timeout_s,
        )
    if not reply.stdout.strip():
        stderr = reply.stderr.strip()
        raise RuntimeError(f"{cfg.summary_command[0]} returned nothing: {stderr}")
    return reply.stdout
