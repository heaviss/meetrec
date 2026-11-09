import pwd

import pytest

from meetrec.config import Config, default_user_name
from meetrec.install import unit, wanted_models


def passwd_entry(gecos: str) -> pwd.struct_passwd:
    return pwd.struct_passwd(("jane", "x", 1000, 1000, gecos, "/home/jane", "/bin/bash"))


@pytest.mark.parametrize(("gecos", "expected"), [("Jane Doe,,,", "Jane Doe"), ("", "jane")])
def test_user_name_defaults_to_full_name(monkeypatch: pytest.MonkeyPatch, gecos: str, expected: str) -> None:
    monkeypatch.setattr(pwd, "getpwuid", lambda _: passwd_entry(gecos))

    assert default_user_name() == expected


@pytest.mark.parametrize(
    ("language", "echo_cancel", "expected"),
    [
        ("ru", False, ["gigaam-v3-e2e-ctc-Q8_0.gguf"]),
        ("en", True, ["parakeet-tdt-0.6b-v2-Q8_0.gguf", "localvqe-v1.4-aec-200K-f32.gguf"]),
    ],
)
def test_setup_fetches_only_needed_models(language: str, echo_cancel: bool, expected: list[str]) -> None:
    assert wanted_models(Config(language=language, echo_cancel=echo_cancel)) == expected


def test_unknown_language_is_rejected() -> None:
    with pytest.raises(ValueError, match="de"):
        Config(language="de")


def test_unit_keeps_setup_path() -> None:
    assert 'Environment="PATH=/home/jane/.local/bin:/odd%%dir"\n' in unit("/home/jane/.local/bin:/odd%dir")
