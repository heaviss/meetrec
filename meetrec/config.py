import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".config/meetrec/config.toml"


@dataclass(frozen=True)
class Config:
    recordings_dir: Path = Path.home() / "Recordings"
    pause_s: float = 30
    min_meeting_s: float = 120
    silent_mic_s: int = 60
    echo_cancel: bool = False
    user_name: str = "Имя Фамилия"
    glossary_repo: Path = Path.home() / "src/work-repo"
    app_denylist: tuple[str, ...] = ("org.PulseAudio.pavucontrol",)
    data_dir: Path = Path.home() / ".local/share/meetrec"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def gigaam_model(self) -> Path:
        return self.models_dir / "gigaam-v3-e2e-ctc-Q8_0.gguf"

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
    if isinstance(default, Path):
        return Path(setting).expanduser()
    if isinstance(default, tuple):
        return tuple(setting)
    return setting


def load_config(path: Path = CONFIG_PATH) -> Config:
    raw: dict[str, Any] = tomllib.loads(path.read_text()) if path.exists() else {}
    defaults = Config()
    return Config(**{key: coerce_setting(getattr(defaults, key), setting) for key, setting in raw.items()})
