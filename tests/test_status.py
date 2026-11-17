"""Tests for ``pytemplate status``: drift of a generated project from its manifest."""

import json
from pathlib import Path

import pytest
from cli_runner import make_runner

from pytemplate.main import app
from pytemplate.status import StatusError, project_status

runner = make_runner()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    result = runner.invoke(app, ["create", "demo", "-o", str(tmp_path), "-y"])
    assert result.exit_code == 0, result.output
    return tmp_path / "demo"


def test_a_fresh_project_is_clean(project: Path) -> None:
    report = project_status(project)

    assert report.clean
    assert report.changed == report.deleted == report.added == ()


def test_changed_deleted_and_added_files_are_reported(project: Path) -> None:
    (project / "README.md").write_text("edited\n", encoding="utf-8")
    (project / "pyproject.toml").unlink()
    (project / "notes.txt").write_text("mine\n", encoding="utf-8")

    report = project_status(project)

    assert report.changed == ("README.md",)
    assert report.deleted == ("pyproject.toml",)
    assert report.added == ("notes.txt",)
    assert not report.clean


def test_caches_environments_the_lock_file_and_the_manifest_are_ignored(project: Path) -> None:
    for directory in (".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"):
        (project / directory).mkdir(exist_ok=True)
        (project / directory / "junk").write_text("x", encoding="utf-8")
    (project / "uv.lock").write_text("lock\n", encoding="utf-8")
    (project / "demo" / "__pycache__").mkdir(exist_ok=True)
    (project / "demo" / "__pycache__" / "a.cpython-313.pyc").write_bytes(b"\0")
    manifest = project / ".pytemplate.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n# touched\n", encoding="utf-8")

    assert project_status(project).clean


def test_status_never_writes(project: Path) -> None:
    (project / "README.md").write_text("edited\n", encoding="utf-8")
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}

    project_status(project)

    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == before


def test_a_directory_without_a_manifest_is_refused(tmp_path: Path) -> None:
    with pytest.raises(StatusError, match="No .pytemplate.toml"):
        project_status(tmp_path)


def test_a_broken_manifest_is_refused(tmp_path: Path) -> None:
    (tmp_path / ".pytemplate.toml").write_text("not = [valid", encoding="utf-8")

    with pytest.raises(StatusError, match="Cannot read"):
        project_status(tmp_path)


def test_a_manifest_path_outside_the_project_is_refused(tmp_path: Path) -> None:
    (tmp_path / ".pytemplate.toml").write_text(
        '[[files]]\npath = "../secret"\nsha256 = "00"\n', encoding="utf-8"
    )

    with pytest.raises(StatusError, match="outside the project"):
        project_status(tmp_path)


def test_status_command_reports_json_and_exit_codes(project: Path, tmp_path: Path) -> None:
    (project / "README.md").write_text("edited\n", encoding="utf-8")

    reported = runner.invoke(app, ["status", str(project), "--json"])
    human = runner.invoke(app, ["status", str(project)])
    missing = runner.invoke(app, ["status", str(tmp_path / "nowhere")])
    missing_json = runner.invoke(app, ["status", str(tmp_path), "--json"])

    assert reported.exit_code == 0
    payload = json.loads(reported.stdout)
    assert payload["clean"] is False
    assert payload["changed"] == ["README.md"]
    assert human.exit_code == 0
    assert "Changed" in human.stdout
    assert "README.md" in human.stdout
    assert missing.exit_code == 1
    assert "Not a directory" in missing.stderr
    assert missing_json.exit_code == 1
    assert json.loads(missing_json.stdout)["ok"] is False


def test_status_command_says_when_nothing_changed(project: Path) -> None:
    result = runner.invoke(app, ["status", str(project)])

    assert result.exit_code == 0
    assert "No changes" in result.stdout
