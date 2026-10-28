"""Upgrade generated projects to a newer template version with `copier update`."""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml
from copier import Settings, run_update
from copier.errors import CopierError

from pytemplate.profiles import get_profile, resolve_components
from pytemplate.rendering import (
    ANSWERS_FILE,
    MANIFEST_FILE,
    generator_version,
    write_generation_manifest,
)


class UpdateError(RuntimeError):
    """Raised when a project cannot be updated safely."""


@dataclass(frozen=True)
class UpdateRequest:
    """Inputs for updating one generated project."""

    project_dir: Path
    to_ref: str | None = None
    apply: bool = False


@dataclass(frozen=True)
class UpdateResult:
    """Outcome of an update request."""

    project_path: Path
    from_ref: str | None
    to_ref: str
    applied: bool


def _read_answers(project_path: Path) -> dict[str, object]:
    answers_path = project_path / ANSWERS_FILE
    if not answers_path.is_file():
        raise UpdateError(
            f"{answers_path} not found. Only projects created by pytemplate-uv 2.1 or later can be "
            "updated; regenerate an older project with the same answers and move your changes over."
        )
    answers = yaml.safe_load(answers_path.read_text(encoding="utf-8")) or {}
    if not isinstance(answers, dict) or not answers.get("_src_path"):
        raise UpdateError(f"{answers_path} does not record a template source (_src_path).")
    return answers


def _git() -> str:
    git = shutil.which("git")
    if git is None:
        raise UpdateError("git is required to update projects; install git and retry.")
    return git


def _project_files(project_path: Path) -> list[Path]:
    """Return tracked and untracked-but-not-ignored files, so caches and .git are skipped."""
    listed = subprocess.run(
        [_git(), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return [project_path / name for name in listed.stdout.split("\0") if name]


def _require_clean_git_tree(project_path: Path) -> None:
    git = _git()
    status = subprocess.run(
        [git, "status", "--porcelain"],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0:
        raise UpdateError(
            f"{project_path} is not a git repository. Run `git init` and commit the project first."
        )
    if status.stdout.strip():
        raise UpdateError(
            "The project has uncommitted changes. Commit or stash them so the update can be "
            "reviewed and reverted with git."
        )


def _refresh_manifest(project_path: Path) -> None:
    manifest_path = project_path / MANIFEST_FILE
    if not manifest_path.is_file():
        return
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    profile = get_profile(str(manifest["profile"]["id"]))
    component_ids = tuple(str(entry["id"]) for entry in manifest.get("components", []))
    write_generation_manifest(
        project_path,
        profile,
        resolve_components(profile, component_ids),
        files=_project_files(project_path),
    )


def update(request: UpdateRequest) -> UpdateResult:
    """Preview or apply a template update; user edits are kept and conflicts marked inline."""
    project_path = request.project_dir.expanduser().resolve()
    if not project_path.is_dir():
        raise UpdateError(f"Project directory does not exist: {project_path}")
    answers = _read_answers(project_path)
    _require_clean_git_tree(project_path)

    version = generator_version()
    to_ref = request.to_ref or f"v{version}"
    if request.to_ref is None and version == "uninstalled":
        raise UpdateError("Cannot infer the target version from a source checkout; pass --to.")
    from_ref = answers.get("_commit")

    try:
        run_update(
            project_path,
            vcs_ref=to_ref,
            settings=Settings(),
            defaults=True,
            overwrite=True,
            conflict="inline",
            pretend=not request.apply,
            quiet=request.apply,
            unsafe=False,
        )
    except (CopierError, ValueError, subprocess.CalledProcessError) as error:
        raise UpdateError(f"Copier could not update {project_path}: {error}") from error

    if request.apply:
        _refresh_manifest(project_path)
    return UpdateResult(
        project_path=project_path,
        from_ref=str(from_ref) if from_ref is not None else None,
        to_ref=to_ref,
        applied=request.apply,
    )
