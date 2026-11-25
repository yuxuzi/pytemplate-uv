"""Tests for the profile question, asked when `-p` is missing (offline)."""

import dataclasses
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from cli_runner import make_runner
from conftest import write_pack

from pytemplate import main, rendering
from pytemplate.main import app

runner = make_runner()


class _Answer:
    def __init__(self, value: str | None) -> None:
        self.value = value

    def ask(self) -> str | None:
        return self.value


def _ask_select(monkeypatch: pytest.MonkeyPatch, answer: str | None) -> list[Any]:
    """Make the terminal, answer the profile question, and return the choices offered."""
    import questionary

    offered: list[Any] = []
    monkeypatch.setattr(main, "_stdin_is_tty", lambda: True)
    monkeypatch.setattr(main, "choose_components", lambda *_args: [])

    def select(message: str, choices: list[Any], **_: object) -> _Answer:
        assert message == "Project profile"
        offered.extend(choices)
        return _Answer(answer)

    monkeypatch.setattr(questionary, "select", select)
    _render_with_defaults(monkeypatch)
    return offered


def _render_with_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render with the template defaults: the terminal answers under test are the profile's."""
    real = main.render

    def defaults(request: rendering.RenderRequest) -> rendering.RenderResult:
        return real(dataclasses.replace(request, no_input=True))

    monkeypatch.setattr(main, "render", defaults)


def _two_profile_pack(root: Path) -> Path:
    """Write a pack with profiles ``tool`` and ``other``, and no ``python`` profile."""
    write_pack(root)
    shutil.copytree(root / "tool", root / "other")
    (root / "other" / "profile.toml").write_text(
        (root / "tool" / "profile.toml")
        .read_text(encoding="utf-8")
        .replace('id = "tool"', 'id = "other"'),
        encoding="utf-8",
    )
    extra = root / "components" / "extra.toml"
    extra.write_text(
        extra.read_text(encoding="utf-8").replace(
            'compatible_profiles = ["tool"]', 'compatible_profiles = ["tool", "other"]'
        ),
        encoding="utf-8",
    )
    questions = root / "questions.yml"
    questions.write_text(
        questions.read_text(encoding="utf-8").replace("choices: [tool]", "choices: [tool, other]"),
        encoding="utf-8",
    )
    return root


def _titles(choices: list[Any]) -> list[str]:
    return [choice.title for choice in choices]


def test_bundled_profiles_are_asked_with_python_first(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    offered = _ask_select(monkeypatch, "library")
    (tmp_path / "out").mkdir()

    result = runner.invoke(app, ["create", "demo", "-o", str(tmp_path / "out")])

    assert result.exit_code == 0, result.output
    titles = _titles(offered)
    assert titles[0].startswith("python - ")
    assert any(title.startswith("library - ") for title in titles)
    assert "Created 'library' project" in result.output


def test_a_cancelled_profile_question_creates_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ask_select(monkeypatch, None)
    (tmp_path / "out").mkdir()

    result = runner.invoke(app, ["create", "demo", "-o", str(tmp_path / "out")])

    assert result.exit_code == 1
    assert "Cancelled; nothing was created." in result.output
    assert not (tmp_path / "out" / "demo").exists()


def test_a_single_profile_is_used_without_a_question(
    pack: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import questionary

    monkeypatch.setattr(
        questionary, "select", lambda *_a, **_k: pytest.fail("the profile question was asked")
    )
    (tmp_path / "out").mkdir()

    result = runner.invoke(
        app, ["create", "demo", "--template", str(pack), "-o", str(tmp_path / "out"), "-y"]
    )

    assert result.exit_code == 0, result.output
    assert "Created 'tool' project" in result.output


def test_yes_without_profile_uses_python_when_the_catalog_has_it(tmp_path: Path) -> None:
    (tmp_path / "out").mkdir()

    result = runner.invoke(app, ["create", "demo", "-y", "--json", "-o", str(tmp_path / "out")])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["profile"] == "python"


def test_yes_without_python_lists_the_profiles(tmp_path: Path) -> None:
    pack = _two_profile_pack(tmp_path / "pack")
    (tmp_path / "out").mkdir()

    result = runner.invoke(
        app, ["create", "demo", "--template", str(pack), "-y", "-o", str(tmp_path / "out")]
    )

    assert result.exit_code == 1
    assert "Unknown profile 'python'" in result.output
    assert "Available profiles: other, tool." in result.output
    assert not (tmp_path / "out" / "demo").exists()


def test_a_local_folder_gets_the_question_and_the_choice_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = _two_profile_pack(tmp_path / "pack")
    offered = _ask_select(monkeypatch, "other")
    (tmp_path / "out").mkdir()

    result = runner.invoke(
        app, ["create", "demo", "--template", str(pack), "-o", str(tmp_path / "out")]
    )

    assert result.exit_code == 0, result.output
    assert _titles(offered) == [
        "other - A tool package.",
        "tool - A tool package.",
    ]
    assert "Created 'other' project" in result.output


def test_without_a_terminal_the_question_is_not_asked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(main, "_stdin_is_tty", lambda: False)
    (tmp_path / "out").mkdir()

    result = runner.invoke(app, ["create", "demo", "-o", str(tmp_path / "out")])

    assert result.exit_code == 1
    assert "standard input is not a terminal" in result.output


@pytest.mark.parametrize("command", ["validate", "plan"])
def test_validate_and_plan_never_ask(
    command: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import questionary

    monkeypatch.setattr(main, "_stdin_is_tty", lambda: True)
    monkeypatch.setattr(
        questionary, "select", lambda *_a, **_k: pytest.fail("the profile question was asked")
    )
    pack = _two_profile_pack(tmp_path / "pack")

    result = runner.invoke(app, [command, "--template", str(pack)])

    assert result.exit_code == 1
    assert "Available profiles: other, tool." in result.output


def test_plan_without_profile_uses_python_on_the_bundled_catalog(tmp_path: Path) -> None:
    result = runner.invoke(app, ["plan", "--json", "-o", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["profile"] == "python"


def test_choices_show_the_hub_lifecycle_and_put_python_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The labels come from the hub entry; python leads whatever order the catalog has."""
    import questionary

    from pytemplate.picker import choose_profile
    from pytemplate.profiles import bundled_catalog

    offered: list[Any] = []

    def select(message: str, choices: list[Any], **_: object) -> _Answer:
        offered.extend(choices)
        return _Answer("library")

    monkeypatch.setattr(questionary, "select", select)
    catalog = bundled_catalog()
    profiles = [catalog.profile("library"), catalog.profile("python")]

    choose_profile(profiles, {"library": "passed", "python": "not-run"})

    titles = _titles(offered)
    assert titles[0].startswith("python - ") and titles[0].endswith("(checks not run)")
    assert titles[1].startswith("library - ") and titles[1].endswith("(checks passed)")
