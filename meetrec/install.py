import hashlib
import logging
import shutil
import subprocess
from pathlib import Path
from types import MappingProxyType
from urllib.request import urlretrieve

from meetrec.config import Config

log = logging.getLogger(__name__)

MODELS = MappingProxyType(
    {
        "gigaam-v3-e2e-ctc-Q8_0.gguf": (
            "https://huggingface.co/handy-computer/gigaam-v3-e2e-ctc-gguf/resolve/main/gigaam-v3-e2e-ctc-Q8_0.gguf",
            "9ccce4750dc813a493d96ca15ee251712bedec15ac9a02fa3d2bd732f08ae5eb",
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
OLD_CACHE = Path.home() / ".cache/meetrec"
UNIT_PATH = Path.home() / ".config/systemd/user/meetrec.service"
UNIT = """\
[Unit]
Description=meetrec: record, transcribe and summarize calls
After=pipewire.service pipewire-pulse.service

[Service]
ExecStart=%h/.local/bin/meetrec run
Environment=PYTHONUNBUFFERED=1
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
    old = OLD_CACHE / "models" / name
    if old.exists() and sha256(old) == digest:
        log.info("moving %s from %s", name, old.parent)
        shutil.move(old, dest)
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
        old = OLD_CACHE / "src/LocalVQE"
        if old.exists():
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(old, src)
        else:
            subprocess.run(["git", "clone", "--recursive", LOCALVQE_REPO, str(src)], check=True)
    subprocess.run(["git", "-C", str(src), "checkout", LOCALVQE_COMMIT], check=True)
    subprocess.run(["git", "-C", str(src), "submodule", "update", "--init", "--recursive"], check=True)


def build_localvqe(src: Path) -> None:
    configure = ("-S", "ggml", "-B", "ggml/build", "-DCMAKE_BUILD_TYPE=Release", "-DLOCALVQE_BUILD_SHARED=ON")
    subprocess.run([*CMAKE, *configure], cwd=src, check=True)
    subprocess.run([*CMAKE, "--build", "ggml/build", "-j6", "--target", "localvqe_shared"], cwd=src, check=True)


def install_localvqe(cfg: Config) -> None:
    if cfg.localvqe_lib.exists():
        return
    fetch_localvqe(cfg.localvqe_src)
    if not cfg.localvqe_lib.exists():
        build_localvqe(cfg.localvqe_src)


def install_unit() -> None:
    UNIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not UNIT_PATH.exists() or UNIT_PATH.read_text() != UNIT:
        UNIT_PATH.write_text(UNIT)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "meetrec"], check=True)


def setup(cfg: Config) -> None:
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in MODELS.items():
        install_model(name, url, digest, cfg.models_dir)
    install_localvqe(cfg)
    install_unit()
    log.info("meetrec is set up; logs: journalctl --user -u meetrec -f")
