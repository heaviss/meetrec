import hashlib
import logging
import os
import subprocess
from pathlib import Path
from types import MappingProxyType
from urllib.request import urlretrieve

from meetrec.config import ASR_MODELS, Config

log = logging.getLogger(__name__)

MODELS = MappingProxyType(
    {
        "gigaam-v3-e2e-ctc-Q8_0.gguf": (
            "https://huggingface.co/handy-computer/gigaam-v3-e2e-ctc-gguf/resolve/main/gigaam-v3-e2e-ctc-Q8_0.gguf",
            "9ccce4750dc813a493d96ca15ee251712bedec15ac9a02fa3d2bd732f08ae5eb",
        ),
        "parakeet-tdt-0.6b-v2-Q8_0.gguf": (
            "https://huggingface.co/handy-computer/parakeet-tdt-0.6b-v2-gguf/resolve/main/"
            "parakeet-tdt-0.6b-v2-Q8_0.gguf",
            "f0d0e99cebb6d3b83f1f7069b82b5d3c2e39a54545b0da039cb4bafd9c4e5caa",
        ),
        "localvqe-v1.4-aec-200K-f32.gguf": (
            "https://huggingface.co/LocalAI-io/LocalVQE/resolve/main/localvqe-v1.4-aec-200K-f32.gguf",
            "b6e43138588a83bfe903ab5e143b4020b91c1e1629f5a575ac5855ff0003c731",
        ),
    }
)
LOCALVQE_REPO = "https://github.com/localai-org/LocalVQE.git"
LOCALVQE_COMMIT = "7f61cd0"
CMAKE = ("uvx", "cmake")
UNIT_PATH = Path.home() / ".config/systemd/user/meetrec.service"
UNIT_TEMPLATE = """\
[Unit]
Description=meetrec: record, transcribe and summarize calls
After=pipewire.service pipewire-pulse.service

[Service]
ExecStart=%h/.local/bin/meetrec run
Environment=PYTHONUNBUFFERED=1
Environment="PATH={path}"
Restart=on-failure
KillMode=control-group

[Install]
WantedBy=default.target
"""


def sha256(path: Path) -> str:
    with open(path, "rb") as model_file:
        return hashlib.file_digest(model_file, "sha256").hexdigest()


def install_model(name: str, url: str, digest: str, models_dir: Path) -> None:
    dest = models_dir / name
    if dest.exists() and sha256(dest) == digest:
        return
    log.info("downloading %s", url)
    partial = dest.with_suffix(".part")
    urlretrieve(url, partial)
    if sha256(partial) != digest:
        partial.unlink()
        raise RuntimeError(f"sha256 mismatch for {name}")
    partial.rename(dest)


def fetch_localvqe(src: Path) -> None:
    if not src.exists():
        subprocess.run(["git", "clone", "--recursive", LOCALVQE_REPO, str(src)], check=True)
    subprocess.run(["git", "-C", str(src), "checkout", LOCALVQE_COMMIT], check=True)
    subprocess.run(["git", "-C", str(src), "submodule", "update", "--init", "--recursive"], check=True)


def build_localvqe(src: Path) -> None:
    configure = ("-S", "ggml", "-B", "ggml/build", "-DCMAKE_BUILD_TYPE=Release", "-DLOCALVQE_BUILD_SHARED=ON")
    subprocess.run([*CMAKE, *configure], cwd=src, check=True)
    subprocess.run([*CMAKE, "--build", "ggml/build", "--parallel", "--target", "localvqe_shared"], cwd=src, check=True)


def install_localvqe(cfg: Config) -> None:
    if cfg.localvqe_lib.exists():
        return
    fetch_localvqe(cfg.localvqe_src)
    if not cfg.localvqe_lib.exists():
        build_localvqe(cfg.localvqe_src)


def unit(path: str) -> str:
    """The setup shell's PATH: at boot systemd gives user services only the system one, without ~/.local/bin."""
    # ponytail: escapes only systemd's %; a PATH with quotes or backslashes would need them escaped too
    return UNIT_TEMPLATE.format(path=path.replace("%", "%%"))


def install_unit() -> None:
    text = unit(os.environ.get("PATH", os.defpath))
    UNIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not UNIT_PATH.exists() or UNIT_PATH.read_text() != text:
        UNIT_PATH.write_text(text)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "meetrec"], check=True)


def wanted_models(cfg: Config) -> list[str]:
    """Only the configured language's model; LocalVQE only with echo_cancel."""
    echo = [cfg.localvqe_model.name] if cfg.echo_cancel else []
    return [ASR_MODELS[cfg.language], *echo]


def setup(cfg: Config) -> None:
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    for name in wanted_models(cfg):
        install_model(name, *MODELS[name], cfg.models_dir)
    if cfg.echo_cancel:
        install_localvqe(cfg)
    install_unit()
    log.info("meetrec is set up; logs: journalctl --user -u meetrec -f")
