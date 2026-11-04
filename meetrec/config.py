import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path.home() / ".config/meetrec/config.toml"


@dataclass(frozen=True)
class Config:
    recordings_dir: Path = Path.home() / "Recordings"
    pause_s: float = 300
    min_meeting_s: float = 120
    silent_mic_s: float = 60
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


def load(path: Path = CONFIG_PATH) -> Config:
    raw = tomllib.loads(path.read_text()) if path.exists() else {}
    defaults = Config()
    values = {}
    for key, value in raw.items():
        default = getattr(defaults, key)
        if isinstance(default, Path):
            value = Path(value).expanduser()
        elif isinstance(default, tuple):
            value = tuple(value)
        values[key] = value
    return Config(**values)
