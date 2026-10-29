"""Upgrade generated projects to a newer template version with `copier update`."""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

import yaml
from copier import Settings, run_update
from copier.errors import CopierError

from pytemplate.errors import RenderError
from pytemplate.packs import BUNDLED, TemplateSource, open_bundled_catalog_at, open_catalog
from pytemplate.profiles import Catalog, Profile
from pytemplate.rendering import (
    ANSWERS_FILE,
    DEFAULT_TEMPLATE_SOURCE,
    MANIFEST_FILE,
    generator_version,
    remove_excluded_directories,
    write_generation_manifest,
)
from pytemplate.resolution import Resolution, resolve


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
            f"{answers_path} not found. Only projects created by pytemplate-uv 3.0 or later can be "
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


def _read_manifest(project_path: Path) -> dict[str, object]:
    manifest_path = project_path / MANIFEST_FILE
    if not manifest_path.is_file():
        return {}
    return tomllib.loads(manifest_path.read_text(encoding="utf-8"))


def _manifest_source(manifest: dict[str, object], answers: dict[str, object]) -> TemplateSource:
    """Return the template source a project was generated from (v1 manifests are bundled)."""
    template = manifest.get("template")
    if isinstance(template, dict) and template.get("kind", BUNDLED) != BUNDLED:
        return TemplateSource(
            kind=str(template["kind"]),
            location=str(template["source"]),
            ref=str(template["ref"]) if template.get("ref") else None,
            pack_id=str(template.get("pack", "")) or None,
            pack_version=str(template.get("pack_version", "")) or None,
        )
    return TemplateSource(kind=BUNDLED, location=str(answers.get("_src_path", "")))


def _legacy_components(profile: Profile, manifest: dict[str, object]) -> list[str]:
    """Return the components a project generated before 3.0 implicitly contains."""
    recorded = manifest.get("components", [])
    ids = (
        [str(entry["id"]) for entry in recorded if isinstance(entry, dict)]
        if isinstance(recorded, list)
        else []
    )
    return sorted({*ids, *profile.default_components, *profile.legacy_components})


def _recorded_resolution(
    catalog: Catalog, profile: Profile, component_ids: list[str]
) -> Resolution:
    """Resolve exactly the recorded components against the target catalog.

    A default added to the profile by a newer release is not added to an existing project: it
    is excluded like any other unselected component.
    """
    components = catalog.component_map()
    kept = replace(
        profile,
        default_components=tuple(
            identifier for identifier in profile.default_components if identifier in component_ids
        ),
    )
    required = {
        needed
        for identifier in component_ids
        if identifier in components
        for needed in components[identifier].requires
    }
    requested = tuple(
        identifier
        for identifier in component_ids
        if identifier not in kept.default_components and identifier not in required
    )
    return resolve(kept, requested, components)


@contextmanager
def _target_catalog(source: TemplateSource, to_ref: str) -> Iterator[Catalog]:
    """Open the catalog of the release being updated to, not the installed one."""
    if not source.is_bundled:
        with open_catalog(source.location, to_ref) as (catalog, _, _):
            yield catalog
    elif to_ref == f"v{generator_version()}":
        with open_catalog() as (catalog, _, _):
            yield catalog
    else:
        with open_bundled_catalog_at(source.location or DEFAULT_TEMPLATE_SOURCE, to_ref) as catalog:
            yield catalog


@dataclass(frozen=True)
class _Preflight:
    """Everything the update needs, computed before Copier writes anything."""

    data: dict[str, object]
    exclude: list[str]
    resolution: Resolution
    recorded_source: TemplateSource


def _preflight(
    answers: dict[str, object],
    manifest: dict[str, object],
    source: TemplateSource,
    to_ref: str,
) -> _Preflight:
    """Resolve the recorded components against the target catalog, or raise `UpdateError`."""
    try:
        with _target_catalog(source, to_ref) as catalog:
            recorded = manifest.get("profile")
            profile_id = answers.get("profile") or (
                recorded.get("id") if isinstance(recorded, dict) else None
            )
            profile = catalog.profile(str(profile_id))
            components = answers.get("components")
            if not isinstance(components, list):
                # Projects from 2.1 development builds never recorded components; keep them all.
                components = _legacy_components(profile, manifest)
            ids = [str(item) for item in components]
            resolution = _recorded_resolution(catalog, profile, ids)
    except (RenderError, ValueError) as error:
        raise UpdateError(f"Cannot prepare the update to {to_ref}: {error}") from error
    data: dict[str, object] = {}
    if list(resolution.component_ids) != answers.get("components"):
        data["components"] = list(resolution.component_ids)
    if source.is_bundled:
        recorded_source = TemplateSource(BUNDLED, source.location, to_ref)
    else:
        recorded_source = replace(source, ref=to_ref)
    return _Preflight(
        data=data,
        exclude=resolution.exclude_patterns(str(answers.get("package_name", ""))),
        resolution=resolution,
        recorded_source=recorded_source,
    )


def _refresh_manifest(project_path: Path, preflight: _Preflight) -> None:
    """Rewrite `.pytemplate.toml` for the new release; touches only local files."""
    if not (project_path / MANIFEST_FILE).is_file():
        return
    write_generation_manifest(
        project_path,
        preflight.resolution,
        preflight.recorded_source,
        files=_project_files(project_path),
    )


def update(request: UpdateRequest) -> UpdateResult:
    """Preview or apply a template update; user edits are kept and conflicts marked inline."""
    project_path = request.project_dir.expanduser().resolve()
    if not project_path.is_dir():
        raise UpdateError(f"Project directory does not exist: {project_path}")
    answers = _read_answers(project_path)
    _require_clean_git_tree(project_path)

    manifest = _read_manifest(project_path)
    source = _manifest_source(manifest, answers)
    version = generator_version()
    if request.to_ref is None and not source.is_bundled:
        raise UpdateError(
            f"This project was generated from the template pack '{source.location}'; pass "
            "--to with the pack tag to update to."
        )
    to_ref = request.to_ref or f"v{version}"
    if request.to_ref is None and version == "uninstalled":
        raise UpdateError("Cannot infer the target version from a source checkout; pass --to.")
    from_ref = answers.get("_commit")
    preflight = _preflight(answers, manifest, source, to_ref)

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
            data=preflight.data,
            exclude=preflight.exclude,
        )
    except (CopierError, ValueError, subprocess.CalledProcessError) as error:
        raise UpdateError(f"Copier could not update {project_path}: {error}") from error

    if request.apply:
        try:
            remove_excluded_directories(project_path, preflight.exclude)
            _refresh_manifest(project_path, preflight)
        except (OSError, subprocess.CalledProcessError) as error:
            raise UpdateError(
                f"Copier applied the update, but refreshing {MANIFEST_FILE} failed: {error}. "
                "Review the changes with `git status` and `git diff`, and revert them with git "
                "if needed."
            ) from error
    return UpdateResult(
        project_path=project_path,
        from_ref=str(from_ref) if from_ref is not None else None,
        to_ref=to_ref,
        applied=request.apply,
    )
