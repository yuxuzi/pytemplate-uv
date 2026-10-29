"""Validated, deterministic rendering of profiles from the bundled catalog or a template pack."""

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
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import yaml
from copier import Settings, run_copy
from copier.errors import CopierError

from pytemplate.errors import RenderError, RequestError
from pytemplate.packs import TemplateSource, open_catalog
from pytemplate.profiles import Catalog, Component, Profile
from pytemplate.resolution import Resolution, resolve

__all__ = [
    "ANSWERS_FILE",
    "DEFAULT_TEMPLATE_SOURCE",
    "MANIFEST_FILE",
    "MANIFEST_SCHEMA",
    "RenderError",
    "RenderPlan",
    "RenderRequest",
    "RenderResult",
    "RequestError",
    "generator_version",
    "plan",
    "remove_empty_directories",
    "render",
    "validate_request",
    "write_generation_manifest",
]

_PROJECT_NAME = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_PACKAGE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
# Package names that would collide with the generated test package or shadow a dependency.
_RESERVED_PACKAGES = frozenset(
    {
        "aiosqlite",
        "alembic",
        "asyncpg",
        "copier",
        "fastapi",
        "httpx",
        "jwt",
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
MANIFEST_SCHEMA = 2
_ANSWERS_HEADER = "# Changes here will be overwritten by Copier; NEVER EDIT MANUALLY\n"


@dataclass(frozen=True)
class RenderRequest:
    """All user-controlled inputs needed to render one project.

    ``template`` selects an external template pack (a directory or git source) and
    ``template_ref`` a git tag or branch of it; leave both unset for the bundled templates.
    ``template_source`` is the git source recorded for bundled projects (for forks).
    """

    profile_id: str
    project_name: str
    output_dir: Path
    components: tuple[str, ...] = ()
    no_input: bool = False
    overwrite: bool = False
    dry_run: bool = False
    data: Mapping[str, str] = field(default_factory=dict)
    template_source: str = DEFAULT_TEMPLATE_SOURCE
    template: str | None = None
    template_ref: str | None = None


@dataclass(frozen=True)
class RenderResult:
    """Outcome of a render request."""

    resolution: Resolution
    project_path: Path
    dry_run: bool
    source: TemplateSource
    manifest_path: Path | None = None

    @property
    def profile(self) -> Profile:
        """Return the rendered profile."""
        return self.resolution.profile

    @property
    def components(self) -> tuple[Component, ...]:
        """Return every resolved component, including those added by ``requires``."""
        return self.resolution.components


@dataclass(frozen=True)
class RenderPlan:
    """What a request would generate, computed without touching the target directory."""

    resolution: Resolution
    project_path: Path
    target_exists: bool
    source: TemplateSource
    package_name: str
    files: tuple[str, ...]


def _package_name(request: RenderRequest) -> str:
    return request.data.get("package_name", request.project_name.replace("-", "_"))


def _validate_package_name(package_name: str) -> None:
    if not _PACKAGE_NAME.fullmatch(package_name):
        raise RequestError(
            f"Package name '{package_name}' must be a lowercase Python identifier "
            "(letters, digits, and underscores, starting with a letter)."
        )
    if (
        keyword.iskeyword(package_name)
        or package_name in sys.stdlib_module_names
        or package_name in _RESERVED_PACKAGES
    ):
        raise RequestError(
            f"Package name '{package_name}' is a Python keyword or would shadow an existing "
            "module; choose another project name or pass --data package_name=<name>."
        )


def _context(request: RenderRequest, resolution: Resolution) -> dict[str, object]:
    """Return template answers; every other default comes from questions.yml."""
    return {
        **request.data,
        "profile": resolution.profile.identifier,
        "project_name": request.project_name,
        "package_name": _package_name(request),
        "components": list(resolution.component_ids),
    }


def _supported_questions(resolution: Resolution) -> tuple[str, ...]:
    component_questions = (
        question for component in resolution.components for question in component.questions
    )
    return tuple(dict.fromkeys([*resolution.profile.questions, *component_questions]))


def _validate(request: RenderRequest, catalog: Catalog) -> tuple[Resolution, Path]:
    """Validate a request against one catalog; the target may already exist."""
    if not _PROJECT_NAME.fullmatch(request.project_name):
        raise RequestError(
            "Project name must be a lowercase slug beginning with a letter and containing "
            "only letters, numbers, and single hyphens between them."
        )
    _validate_package_name(_package_name(request))
    profile = catalog.profile(request.profile_id)
    resolution = resolve(profile, request.components, catalog.component_map())
    supported = _supported_questions(resolution)
    unknown = sorted(set(request.data) - set(supported))
    if "project_name" in request.data or unknown:
        rejected = ", ".join(unknown) if unknown else "project_name"
        raise RequestError(
            f"Unsupported template data for profile '{profile.identifier}': {rejected}. "
            f"Supported keys: {', '.join(q for q in supported if q != 'project_name')}."
        )
    output_dir = request.output_dir.expanduser().resolve()
    if not output_dir.is_dir():
        raise RequestError(f"Output directory does not exist or is not a directory: {output_dir}")
    return resolution, output_dir / request.project_name


def _check_target(request: RenderRequest, project_path: Path) -> None:
    if project_path.exists() and not request.overwrite:
        raise RequestError(
            f"Output already exists: {project_path}. Re-run with --force only if "
            "overwriting is intended."
        )


def validate_request(request: RenderRequest) -> tuple[Resolution, Path]:
    """Validate a request without rendering and return its resolution and target path."""
    with open_catalog(request.template, request.template_ref) as (catalog, _, _):
        resolution, project_path = _validate(request, catalog)
    _check_target(request, project_path)
    return resolution, project_path


def generator_version() -> str:
    """Return the installed pytemplate-uv version, or 'uninstalled' in a source checkout."""
    try:
        return version("pytemplate-uv")
    except PackageNotFoundError:
        return "uninstalled"


def _toml(value: object) -> str:
    """Encode a string, boolean, or list of strings as TOML (JSON strings are valid TOML)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | tuple):
        return json.dumps([str(item) for item in value])
    return json.dumps(str(value))


def _recorded_answers(project_path: Path) -> dict[str, object]:
    """Return the user-facing answers from the Copier answers file, without `_` metadata."""
    answers_path = project_path / ANSWERS_FILE
    if not answers_path.is_file():
        return {}
    answers = yaml.safe_load(answers_path.read_text(encoding="utf-8")) or {}
    return {
        str(key): value
        for key, value in sorted(answers.items())
        if not str(key).startswith("_") and isinstance(value, str | bool | list)
    }


def _component_reason(resolution: Resolution, identifier: str) -> str:
    if identifier in resolution.profile.default_components:
        return "default"
    return "required" if identifier in resolution.added else "requested"


def write_generation_manifest(
    project_path: Path,
    resolution: Resolution,
    source: TemplateSource,
    files: Sequence[Path] | None = None,
) -> Path:
    """Record the resolved factory contract and an owned-file hash inventory in a project.

    ``files`` defaults to every file under ``project_path``, which is correct right after
    rendering; callers updating an existing project pass the files they want inventoried.
    """
    manifest_path = project_path / MANIFEST_FILE
    if files is None:
        files = [path for path in project_path.rglob("*") if path.is_file()]
    answers = _recorded_answers(project_path)
    package = str(answers.get("package_name", project_path.name.replace("-", "_")))
    profile = resolution.profile
    lines = [
        f"schema = {MANIFEST_SCHEMA}",
        "",
        "[generator]",
        'name = "pytemplate-uv"',
        f"version = {_toml(generator_version())}",
        "",
        "[template]",
        f"kind = {_toml(source.kind)}",
        f"source = {_toml(source.location)}",
    ]
    for key, value in (
        ("ref", source.ref),
        ("pack", source.pack_id),
        ("pack_version", source.pack_version),
    ):
        if value:
            lines.append(f"{key} = {_toml(value)}")
    lines += [
        "",
        "[profile]",
        f"id = {_toml(profile.identifier)}",
        f"version = {_toml(profile.version)}",
        f"supported_python = {_toml(profile.supported_python)}",
    ]
    for component in resolution.components:
        lines += [
            "",
            "[[components]]",
            f"id = {_toml(component.identifier)}",
            f"version = {_toml(component.version)}",
            f"status = {_toml(component.status)}",
            f"reason = {_toml(_component_reason(resolution, component.identifier))}",
        ]
    lines += ["", "[answers]", *(f"{key} = {_toml(value)}" for key, value in answers.items())]
    for path in sorted(files):
        if path.is_file() and path.name != MANIFEST_FILE:
            relative = path.relative_to(project_path).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines += [
                "",
                "[[files]]",
                f"path = {_toml(relative)}",
                f'sha256 = "{digest}"',
                f"owner = {_toml(resolution.owner(relative, package))}",
            ]
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path


def _record_template_source(project_path: Path, location: str, ref: str | None) -> None:
    """Point the answers file at the template's git source so `copier update` can merge."""
    answers_path = project_path / ANSWERS_FILE
    answers = yaml.safe_load(answers_path.read_text(encoding="utf-8")) or {}
    answers["_src_path"] = location
    answers.pop("_commit", None)
    if ref:
        answers["_commit"] = ref
    answers_path.write_text(
        _ANSWERS_HEADER + yaml.safe_dump(answers, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )


def remove_empty_directories(root: Path) -> None:
    """Delete directories left empty because every file in them was excluded."""
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir() and not path.is_symlink() and not any(path.iterdir()):
            path.rmdir()


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


def _render_into(
    destination: Path,
    request: RenderRequest,
    resolution: Resolution,
    source: TemplateSource,
    template_path: Path,
) -> Path:
    """Render with Copier into ``destination`` and write the answers and manifest files."""
    try:
        run_copy(
            str(template_path),
            destination,
            data=_context(request, resolution),
            settings=Settings(),
            defaults=request.no_input,
            quiet=True,
            unsafe=False,
            exclude=resolution.exclude_patterns(_package_name(request)),
        )
    except ValueError as error:
        raise RequestError(
            f"Copier rejected the answers for profile '{resolution.profile.identifier}': {error}"
        ) from error
    except CopierError as error:
        raise RenderError(
            f"Copier could not render profile '{resolution.profile.identifier}': {error}"
        ) from error
    if not (destination / ANSWERS_FILE).is_file():
        raise RenderError(
            f"Profile '{resolution.profile.identifier}' did not write {ANSWERS_FILE}; add a "
            "`{{ _copier_conf.answers_file }}.jinja` file containing "
            "`{{ _copier_answers|to_nice_yaml }}` to its template."
        )
    _record_template_source(destination, source.location, source.ref)
    remove_empty_directories(destination)
    return write_generation_manifest(destination, resolution, source)


def _source(request: RenderRequest, opened: TemplateSource) -> TemplateSource:
    """Return the source to record: bundled projects point at the versioned git tag."""
    if not opened.is_bundled:
        return opened
    installed = generator_version()
    ref = None if installed == "uninstalled" else f"v{installed}"
    return TemplateSource(kind=opened.kind, location=request.template_source, ref=ref)


def plan(request: RenderRequest) -> RenderPlan:
    """Resolve a request and list the files it would generate, without touching the target.

    The project is rendered into a temporary directory that is always removed.
    """
    with open_catalog(request.template, request.template_ref) as (catalog, opened, root):
        resolution, project_path = _validate(request, catalog)
        source = _source(request, opened)
        with tempfile.TemporaryDirectory(prefix="pytemplate-plan-") as scratch:
            staged = Path(scratch) / request.project_name
            try:
                _render_into(staged, request, resolution, source, root)
            except OSError as error:
                raise RenderError(f"Could not render the plan: {error}") from error
            files = tuple(
                sorted(
                    path.relative_to(staged).as_posix()
                    for path in staged.rglob("*")
                    if path.is_file()
                )
            )
    return RenderPlan(
        resolution=resolution,
        project_path=project_path,
        target_exists=project_path.exists(),
        source=source,
        package_name=_package_name(request),
        files=files,
    )


def render(request: RenderRequest) -> RenderResult:
    """Validate and render a profile with Copier, publishing the project only on success."""
    with open_catalog(request.template, request.template_ref) as (catalog, opened, root):
        resolution, project_path = _validate(request, catalog)
        _check_target(request, project_path)
        source = _source(request, opened)
        if request.dry_run:
            return RenderResult(
                resolution=resolution, project_path=project_path, dry_run=True, source=source
            )

        staging_root = Path(tempfile.mkdtemp(prefix=".pytemplate-", dir=project_path.parent))
        staged = staging_root / project_path.name
        try:
            manifest_path = _render_into(staged, request, resolution, source, root)
            _publish(staged, project_path)
        except OSError as error:
            raise RenderError(f"Could not write generated project: {error}") from error
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)
    return RenderResult(
        resolution=resolution,
        project_path=project_path,
        dry_run=False,
        source=source,
        manifest_path=project_path / manifest_path.name,
    )
