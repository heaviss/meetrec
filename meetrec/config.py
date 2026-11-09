import os
import pwd
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

CONFIG_PATH = Path.home() / ".config/meetrec/config.toml"
PROMPT_FILE = "{prompt_file}"
CLAUDE = (
    "claude",
    "-p",
    "--no-session-persistence",
    "--tools",
    "",
    "--setting-sources",
    "project",
    "--system-prompt-file",
    PROMPT_FILE,
)
ASR_MODELS = MappingProxyType({"ru": "gigaam-v3-e2e-ctc-Q8_0.gguf", "en": "parakeet-tdt-0.6b-v2-Q8_0.gguf"})


def default_user_name() -> str:
    """The full name from the passwd GECOS field, or the login when it is empty."""
    entry = pwd.getpwuid(os.getuid())
    return entry.pw_gecos.split(",")[0] or entry.pw_name


@dataclass(frozen=True)
class Config:
    recordings_dir: Path = Path.home() / "Recordings"
    pause_s: float = 30
    min_meeting_s: float = 120
    silent_mic_s: int = 60
    echo_cancel: bool = False
    user_name: str = field(default_factory=default_user_name)
    glossary_repo: Path | None = None
    summary_command: tuple[str, ...] = CLAUDE
    summary_timeout_s: float = 900
    language: str = "ru"
    app_denylist: tuple[str, ...] = ("org.PulseAudio.pavucontrol",)
    data_dir: Path = Path.home() / ".local/share/meetrec"

    def __post_init__(self) -> None:
        if self.language not in ASR_MODELS:
            known = ", ".join(ASR_MODELS)
            raise ValueError(f"language {self.language!r} is not one of {known}")

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    def asr_model(self, language: str) -> Path:
        return self.models_dir / ASR_MODELS[language]

    @property
    def localvqe_model(self) -> Path:
        return self.models_dir / "localvqe-v1.4-aec-200K-f32.gguf"

    @property
    def localvqe_src(self) -> Path:
        return self.data_dir / "src/LocalVQE"

    @property
    def localvqe_lib(self) -> Path:
        return self.localvqe_src / "ggml/build/bin/liblocalvqe.so"

    @property
    def state_path(self) -> Path:
        return self.data_dir / "state.json"


def coerce_setting(default: Any, setting: Any) -> Any:
    if isinstance(default, Path | None):
        return Path(setting).expanduser()
    if isinstance(default, tuple):
        return tuple(setting)
    return setting


def load_config(path: Path = CONFIG_PATH) -> Config:
    raw: dict[str, Any] = tomllib.loads(path.read_text()) if path.exists() else {}
    defaults = Config()
    return Config(**{key: coerce_setting(getattr(defaults, key), setting) for key, setting in raw.items()})
