"""Opt-in steps that run in a freshly created project: ``--lock`` and ``--git``.

They never run by default, and never for a dry run. A failing step leaves the project in place
and raises ``PostCreateError`` (CLI exit code 2), naming what was created and what failed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from pytemplate.errors import RenderError

COMMIT_MESSAGE = "Initial commit from pytemplate-uv"
GIT_TIMEOUT_SECONDS = 60
LOCK_TIMEOUT_SECONDS = 300


class PostCreateError(RenderError):
    """Raised when an opt-in step after creation fails; the created project stays on disk."""


def _run(project: Path, command: list[str], timeout: int, done: list[str]) -> None:
    """Run one command in the project, converting every failure into ``PostCreateError``."""
    shown = " ".join(command[:2] if command[0] == "git" else command)
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    created = f"The project was created at {project}"
    if done:
        created += f" and {', '.join(done)}"
    try:
        completed = subprocess.run(
            command,
            cwd=project,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as error:
        raise PostCreateError(
            f"{created}, but `{shown}` could not run: `{command[0]}` was not found on PATH."
        ) from error
    except subprocess.TimeoutExpired as error:
        raise PostCreateError(
            f"{created}, but `{shown}` did not finish within {timeout} seconds."
        ) from error
    except OSError as error:
        raise PostCreateError(f"{created}, but `{shown}` could not run: {error}") from error
    if completed.returncode != 0:
        detail = (completed.stderr.strip() or completed.stdout.strip()).splitlines()
        reason = detail[-1] if detail else f"exit status {completed.returncode}"
        raise PostCreateError(f"{created}, but `{shown}` failed: {reason}")


def lock_dependencies(project: Path, done: list[str] | None = None) -> str:
    """Run ``uv lock`` in the project and return a human description of what happened."""
    _run(project, ["uv", "lock"], LOCK_TIMEOUT_SECONDS, done or [])
    return "locked the dependencies (uv.lock)"


def initialise_git(project: Path, done: list[str] | None = None) -> str:
    """Create a git repository with every file committed; return what happened."""
    steps = done or []
    _run(project, ["git", "init"], GIT_TIMEOUT_SECONDS, steps)
    _run(project, ["git", "add", "--all"], GIT_TIMEOUT_SECONDS, [*steps, "ran `git init`"])
    _run(
        project,
        ["git", "commit", "--quiet", "-m", COMMIT_MESSAGE],
        GIT_TIMEOUT_SECONDS,
        [*steps, "ran `git init`"],
    )
    return "made the first git commit"


def run_post_steps(project: Path, *, git: bool, lock: bool) -> list[str]:
    """Run the requested steps (lock first, so the first commit includes ``uv.lock``)."""
    done: list[str] = []
    if lock:
        done.append(lock_dependencies(project, done))
    if git:
        done.append(initialise_git(project, done))
    return done
