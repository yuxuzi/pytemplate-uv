"""Tests for the opt-in --git and --lock steps; subprocess is always mocked."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from pytemplate import post_create
from pytemplate.main import app

runner = CliRunner()


class Recorder:
    """Stand-in for subprocess.run that records calls and can fail one command."""

    def __init__(self, fail: str | None = None, timeout: bool = False) -> None:
        """Fail the command starting with ``fail`` (by timeout or non-zero status)."""
        self.calls: list[tuple[list[str], dict[str, Any]]] = []
        self.fail = fail
        self.timeout = timeout

    def __call__(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        """Record the call and return a successful or failed result."""
        self.calls.append((command, kwargs))
        if self.fail and command[:2] == self.fail.split():
            if self.timeout:
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            return subprocess.CompletedProcess(command, 1, "", "fatal: boom\n")
        return subprocess.CompletedProcess(command, 0, "", "")


def _install(monkeypatch: pytest.MonkeyPatch, recorder: Recorder) -> None:
    monkeypatch.setattr(post_create.subprocess, "run", recorder)


def test_git_and_lock_run_in_the_project_with_prompts_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder()
    _install(monkeypatch, recorder)

    result = runner.invoke(app, ["create", "demo", "-o", str(tmp_path), "-y", "--git", "--lock"])

    assert result.exit_code == 0, result.output
    commands = [call[0] for call in recorder.calls]
    assert commands == [
        ["uv", "lock"],
        ["git", "init"],
        ["git", "add", "--all"],
        ["git", "commit", "--quiet", "-m", "Initial commit from pytemplate-uv"],
    ]
    for _, kwargs in recorder.calls:
        assert kwargs["cwd"] == (tmp_path / "demo").resolve()
        assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
        assert kwargs["timeout"] > 0
    assert "first git commit" in result.stdout


def test_nothing_runs_by_default_or_for_a_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder()
    _install(monkeypatch, recorder)

    plain = runner.invoke(app, ["create", "one", "-o", str(tmp_path), "-y"])
    dry = runner.invoke(
        app, ["create", "two", "-o", str(tmp_path), "-y", "--git", "--lock", "--dry-run"]
    )

    assert plain.exit_code == dry.exit_code == 0
    assert recorder.calls == []


def test_a_failing_step_keeps_the_project_and_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, Recorder(fail="git commit"))

    result = runner.invoke(app, ["create", "demo", "-o", str(tmp_path), "-y", "--git"])

    assert result.exit_code == 2
    assert (tmp_path / "demo" / "pyproject.toml").is_file()
    assert "The project was created at" in result.stderr
    assert "git commit" in result.stderr
    assert "fatal: boom" in result.stderr


def test_a_failing_step_reports_json_errors_on_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, Recorder(fail="uv lock"))

    result = runner.invoke(app, ["create", "demo", "-o", str(tmp_path), "--json", "--lock"])

    payload = json.loads(result.stdout)
    assert result.exit_code == 2
    assert payload["error"]["type"] == "PostCreateError"


def test_a_timeout_and_a_missing_tool_are_explained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, Recorder(fail="git init", timeout=True))
    with pytest.raises(post_create.PostCreateError, match="did not finish within"):
        post_create.initialise_git(tmp_path)

    def missing(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(post_create.subprocess, "run", missing)
    with pytest.raises(post_create.PostCreateError, match="`uv` was not found"):
        post_create.lock_dependencies(tmp_path)


def test_the_message_says_what_already_succeeded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, Recorder(fail="git add"))

    with pytest.raises(post_create.PostCreateError, match="ran `git init`"):
        post_create.initialise_git(tmp_path)
