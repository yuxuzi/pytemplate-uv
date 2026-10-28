"""Validated, deterministic rendering of bundled project profiles."""

from __future__ import annotations

import hashlib
import json
import keyword
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib import resources
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import yaml
from copier import Settings, run_copy
from copier.errors import CopierError

from pytemplate.profiles import Component, Profile, get_profile, resolve_components

_PROJECT_NAME = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_PACKAGE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
# Package names that would collide with the generated test package or shadow a dependency.
_RESERVED_PACKAGES = frozenset(
    {
        "aiosqlite",
        "copier",
        "fastapi",
        "pydantic",
        "pydantic_settings",
        "pytest",
        "rich",
        "sqlalchemy",
        "sqlmodel",
        "test",
        "tests",
        "typer",
        "uvicorn",
    }
)


DEFAULT_TEMPLATE_SOURCE = "gh:yuxuzi/pytemplate-uv"
ANSWERS_FILE = ".copier-answers.yml"
MANIFEST_FILE = ".pytemplate.toml"
_ANSWERS_HEADER = "# Changes here will be overwritten by Copier; NEVER EDIT MANUALLY\n"


class RenderError(RuntimeError):
    """Raised when a validated render request cannot be completed."""


@dataclass(frozen=True)
class RenderRequest:
    """All user-controlled inputs needed to render one project."""

    profile_id: str
    project_name: str
    output_dir: Path
    components: tuple[str, ...] = ()
    no_input: bool = False
    overwrite: bool = False
    dry_run: bool = False
    data: Mapping[str, str] = field(default_factory=dict)
    template_source: str = DEFAULT_TEMPLATE_SOURCE


@dataclass(frozen=True)
class RenderResult:
    """Outcome of a render request."""

    profile: Profile
    components: tuple[Component, ...]
    project_path: Path
    dry_run: bool
    manifest_path: Path | None = None


def _package_name(request: RenderRequest) -> str:
    return request.data.get("package_name", request.project_name.replace("-", "_"))


def _validate_package_name(package_name: str) -> None:
    if not _PACKAGE_NAME.fullmatch(package_name):
        raise RenderError(
            f"Package name '{package_name}' must be a lowercase Python identifier "
            "(letters, digits, and underscores, starting with a letter)."
        )
    if (
        keyword.iskeyword(package_name)
        or package_name in sys.stdlib_module_names
        or package_name in _RESERVED_PACKAGES
    ):
        raise RenderError(
            f"Package name '{package_name}' is a Python keyword or would shadow an existing "
            "module; choose another project name or pass --data package_name=<name>."
        )


def _context(request: RenderRequest, profile: Profile) -> dict[str, str]:
    """Return template answers; every other default comes from questions.yml."""
    return {
        **request.data,
        "profile": profile.identifier,
        "project_name": request.project_name,
        "package_name": _package_name(request),
    }


def validate_request(request: RenderRequest) -> tuple[Profile, tuple[Component, ...], Path]:
    """Validate a request without writing files and return its resolved target."""
    if not _PROJECT_NAME.fullmatch(request.project_name):
        raise RenderError(
            "Project name must be a lowercase slug beginning with a letter and containing "
            "only letters, numbers, and single hyphens between them."
        )
    _validate_package_name(_package_name(request))
    profile = get_profile(request.profile_id)
    components = resolve_components(profile, request.components)
    unknown = sorted(set(request.data) - set(profile.questions))
    if "project_name" in request.data or unknown:
        rejected = ", ".join(unknown) if unknown else "project_name"
        raise RenderError(
            f"Unsupported template data for profile '{profile.identifier}': {rejected}. "
            f"Supported keys: {', '.join(q for q in profile.questions if q != 'project_name')}."
        )
    output_dir = request.output_dir.expanduser().resolve()
    if not output_dir.is_dir():
        raise RenderError(f"Output directory does not exist or is not a directory: {output_dir}")
    project_path = output_dir / request.project_name
    if project_path.exists() and not request.overwrite:
        raise RenderError(
            f"Output already exists: {project_path}. Re-run with --force only if "
            "overwriting is intended."
        )
    return profile, components, project_path


def generator_version() -> str:
    """Return the installed pytemplate-uv version, or 'uninstalled' in a source checkout."""
    try:
        return version("pytemplate-uv")
    except PackageNotFoundError:
        return "uninstalled"


def write_generation_manifest(
    project_path: Path,
    profile: Profile,
    components: tuple[Component, ...],
    files: Sequence[Path] | None = None,
) -> Path:
    """Record the resolved factory contract and a hash inventory inside a generated project.

    ``files`` defaults to every file under ``project_path``, which is correct right after
    rendering; callers updating an existing project pass the files they want inventoried.
    """
    manifest_path = project_path / MANIFEST_FILE
    if files is None:
        files = [path for path in project_path.rglob("*") if path.is_file()]
    lines = [
        "[generator]",
        'name = "pytemplate-uv"',
        f"version = {json.dumps(generator_version())}",
        "",
        "[profile]",
        f"id = {json.dumps(profile.identifier)}",
        f"version = {json.dumps(profile.version)}",
        f"supported_python = {json.dumps(list(profile.supported_python))}",
    ]
    for component in components:
        lines.extend(
            [
                "",
                "[[components]]",
                f"id = {json.dumps(component.identifier)}",
                f"version = {json.dumps(component.version)}",
                f"dependency_groups = {json.dumps(list(component.dependency_groups))}",
                f"template_fragments = {json.dumps(list(component.template_fragments))}",
            ]
        )
    for path in sorted(files):
        if path.is_file() and path.name != MANIFEST_FILE:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.extend(
                [
                    "",
                    "[[files]]",
                    f"path = {json.dumps(path.relative_to(project_path).as_posix())}",
                    f'sha256 = "{digest}"',
                ]
            )
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path


def _record_template_source(project_path: Path, source: str) -> None:
    """Point the answers file at the versioned git source so `copier update` can merge later."""
    answers_path = project_path / ANSWERS_FILE
    answers = yaml.safe_load(answers_path.read_text(encoding="utf-8")) or {}
    answers["_src_path"] = source
    version = generator_version()
    if version != "uninstalled":
        answers["_commit"] = f"v{version}"
    answers_path.write_text(
        _ANSWERS_HEADER + yaml.safe_dump(answers, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _publish(staged: Path, project_path: Path) -> None:
    """Move a fully rendered project into place, replacing any existing output."""
    if not project_path.exists():
        os.replace(staged, project_path)
        return
    backup = project_path.with_name(f".{project_path.name}.pytemplate-backup")
    if backup.exists():
        raise RenderError(f"A previous backup is in the way; remove it first: {backup}")
    os.replace(project_path, backup)
    try:
        os.replace(staged, project_path)
    except OSError:
        os.replace(backup, project_path)
        raise
    _remove(backup)


def render(request: RenderRequest) -> RenderResult:
    """Validate and render a profile with Copier, publishing the project only on success."""
    profile, components, project_path = validate_request(request)
    if request.dry_run:
        return RenderResult(
            profile=profile,
            components=components,
            project_path=project_path,
            dry_run=True,
        )

    staging_root = Path(tempfile.mkdtemp(prefix=".pytemplate-", dir=project_path.parent))
    staged = staging_root / project_path.name
    try:
        with resources.as_file(profile.template_resource) as template_path:
            run_copy(
                str(template_path),
                staged,
                data=_context(request, profile),
                settings=Settings(),
                defaults=request.no_input,
                quiet=True,
                unsafe=False,
            )
        _record_template_source(staged, request.template_source)
        manifest_path = write_generation_manifest(staged, profile, components)
        _publish(staged, project_path)
    except (CopierError, ValueError) as error:
        raise RenderError(
            f"Copier could not render profile '{profile.identifier}': {error}"
        ) from error
    except OSError as error:
        raise RenderError(f"Could not write generated project: {error}") from error
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
    return RenderResult(
        profile=profile,
        components=components,
        project_path=project_path,
        dry_run=False,
        manifest_path=project_path / manifest_path.name,
    )
