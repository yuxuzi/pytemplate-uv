"""Tests for Copier-backed rendering, determinism, and generated agent guidance."""

import hashlib
import re
import tomllib
from pathlib import Path

import pytest

import pytemplate.rendering as rendering
from pytemplate.profiles import get_profile
from pytemplate.rendering import RenderError, RenderRequest, RequestError, render

PROFILES = ("python", "fastapi")
SOURCE_ROOT = Path(__file__).parent.parent / "pytemplate"


def _render(profile: str, output_dir: Path, **kwargs: object) -> Path:
    result = render(
        RenderRequest(
            profile_id=profile,
            project_name="market-data-api",
            output_dir=output_dir,
            no_input=True,
            **kwargs,
        )
    )
    return result.project_path


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_generator_no_longer_imports_cookiecutter() -> None:
    for module in SOURCE_ROOT.glob("*.py"):
        assert "cookiecutter" not in module.read_text(encoding="utf-8"), module


@pytest.mark.parametrize("profile", PROFILES)
def test_rendering_is_deterministic(profile: str, tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()

    first = _render(profile, tmp_path / "a")
    second = _render(profile, tmp_path / "b")

    assert _tree(first) == _tree(second)


@pytest.mark.parametrize("profile", PROFILES)
def test_rendered_files_have_no_template_leftovers(profile: str, tmp_path: Path) -> None:
    project = _render(profile, tmp_path)
    tree = _tree(project)

    assert not [name for name in tree if name.endswith(".jinja") or "{{" in name]
    for name, content in tree.items():
        text = content.decode("utf-8")
        assert not re.search(r"(?<!\$)\{\{|\{%", text), name
    workflow = tree[".github/workflows/ci.yml"].decode("utf-8")
    assert "${{ matrix.os }}" in workflow
    assert "${{ matrix.python-version }}" in workflow


@pytest.mark.parametrize("profile", PROFILES)
def test_generated_claude_md_is_profile_aware(profile: str, tmp_path: Path) -> None:
    project = _render(profile, tmp_path)
    guidance = (project / "CLAUDE.md").read_text(encoding="utf-8")

    assert "`market_data_api`" in guidance
    workflow = (project / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for command in get_profile(profile).lifecycle_commands:
        rendered = command.format(package="market_data_api")
        assert rendered in guidance
        assert rendered in workflow
    assert "SECRET_KEY" not in guidance
    assert "replace-this-before-production" not in guidance
    assert len(guidance.splitlines()) <= 80


@pytest.mark.parametrize("profile", PROFILES)
def test_generated_gitignore_excludes_env_files(profile: str, tmp_path: Path) -> None:
    project = _render(profile, tmp_path)

    assert ".env" in (project / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_template_data_overrides_defaults(tmp_path: Path) -> None:
    project = _render("python", tmp_path, data={"description": "Factor research toolkit"})

    assert "Factor research toolkit" in (project / "README.md").read_text(encoding="utf-8")


def test_unknown_template_data_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(RenderError, match="Unsupported template data"):
        _render("python", tmp_path, data={"unknown": "value"})


def test_invalid_package_name_is_reported(tmp_path: Path) -> None:
    with pytest.raises(RenderError, match="lowercase Python identifier"):
        _render("python", tmp_path, data={"package_name": "Not-Valid"})
    assert list(tmp_path.iterdir()) == []


def test_force_replaces_the_previous_project(tmp_path: Path) -> None:
    project = _render("python", tmp_path)
    (project / "stale.txt").write_text("old", encoding="utf-8")

    _render("python", tmp_path, overwrite=True)

    assert not (project / "stale.txt").exists()
    assert (project / "CLAUDE.md").is_file()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["market-data-api"]


def test_failed_render_leaves_no_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        destination = Path(args[1])
        destination.mkdir(parents=True)
        (destination / "partial.txt").write_text("partial", encoding="utf-8")
        raise OSError("disk full")

    monkeypatch.setattr(rendering, "run_copy", fail)

    with pytest.raises(RenderError, match="disk full"):
        _render("python", tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("profile", PROFILES)
def test_generated_projects_depend_only_on_uv(profile: str, tmp_path: Path) -> None:
    project = _render(profile, tmp_path, components=("container",))
    tree = _tree(project)

    assert not [name for name in tree if Path(name).name == "Makefile"]
    assert not re.search(r"\bmake\b", tree["Dockerfile"].decode("utf-8"))
    assert not re.search(r"\bpip install\b", tree["README.md"].decode("utf-8"))
    pyproject = tree["pyproject.toml"].decode("utf-8")
    assert "[dependency-groups]" in pyproject
    assert "[project.optional-dependencies]" not in pyproject


def test_manifest_records_a_hash_for_every_rendered_file(tmp_path: Path) -> None:
    project = _render("python", tmp_path)
    manifest = tomllib.loads((project / ".pytemplate.toml").read_text(encoding="utf-8"))
    recorded = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    rendered = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in _tree(project).items()
        if name != ".pytemplate.toml"
    }

    assert recorded == rendered


@pytest.mark.parametrize("name", ["class", "tests", "typer", "json", "data-"])
def test_unusable_project_names_are_rejected_before_rendering(name: str, tmp_path: Path) -> None:
    with pytest.raises(RenderError):
        render(RenderRequest(profile_id="python", project_name=name, output_dir=tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_package_name_override_is_validated(tmp_path: Path) -> None:
    with pytest.raises(RenderError, match="shadow"):
        _render("python", tmp_path, data={"package_name": "sqlmodel"})


@pytest.mark.parametrize(
    "data",
    [{"description": 'Say "hi"'}, {"license": "not a license!"}, {"python_version": "3.9"}],
)
def test_template_validators_reject_unsafe_answers(data: dict[str, str], tmp_path: Path) -> None:
    with pytest.raises(RequestError, match="Copier rejected the answers"):
        _render("python", tmp_path, data=data)
    assert list(tmp_path.iterdir()) == []
