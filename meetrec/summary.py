import subprocess
import tempfile
from pathlib import Path

from meetrec.config import Config

PROMPT = Path(__file__).with_name("prompt.md")


def glossary(repo: Path) -> str:
    if not (repo / ".git").exists():
        return ""
    files = subprocess.run(
        ["git", "ls-files", "GLOSSARY-MAP.md", "*GLOSSARY.md"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return "\n\n".join(f"### {name}\n{(repo / name).read_text()}" for name in files)


def summarize(transcript: str, cfg: Config) -> str:
    terms = glossary(cfg.glossary_repo)
    text = f"<glossary>\n{terms}\n</glossary>\n\n<transcript>\n{transcript}\n</transcript>" if terms else transcript
    with tempfile.TemporaryDirectory() as tmp:
        prompt = Path(tmp) / "prompt.md"
        prompt.write_text(PROMPT.read_text().replace("{user_name}", cfg.user_name))
        out = subprocess.run(
            [
                "claude",
                "-p",
                "--no-session-persistence",
                "--tools",
                "",
                "--setting-sources",
                "project",
                "--system-prompt-file",
                str(prompt),
            ],
            input=text,
            cwd=tmp,
            capture_output=True,
            text=True,
            check=True,
            timeout=900,
        )
    if not out.stdout.strip():
        raise RuntimeError(f"claude returned nothing: {out.stderr.strip()}")
    return out.stdout
