import pytest

from meetrec.process import Plan, plan


@pytest.mark.parametrize(
    ("redo", "have", "expected"),
    [
        ("missing", (False, False, False), Plan(transcribe=True, transcript=True, summary=True)),
        ("missing", (True, True, False), Plan(transcribe=False, transcript=False, summary=True)),
        ("missing", (True, True, True), Plan(transcribe=False, transcript=False, summary=False)),
        ("missing", (True, False, True), Plan(transcribe=False, transcript=True, summary=True)),
        ("transcript", (True, True, True), Plan(transcribe=False, transcript=True, summary=True)),
        ("all", (True, True, True), Plan(transcribe=True, transcript=True, summary=True)),
    ],
)
def test_plan(redo: str, have: tuple[bool, bool, bool], expected: Plan) -> None:
    assert plan(redo, *have) == expected
