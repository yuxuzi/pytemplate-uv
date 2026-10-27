"""Validated, deterministic rendering of bundled project profiles."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
import json
import os
from pathlib import Path
import re
import tempfile

from cookiecutter.exceptions import CookiecutterException
from cookiecutter.main import cookiecutter

from pytemplate.profiles import Profile, get_profile

_PROJECT_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


class RenderError(RuntimeError):
    """Raised when a validated render request cannot be completed."""


@dataclass(frozen=True)
class RenderRequest:
    """All user-controlled inputs needed to render one project."""

    profile_id: str
    project_name: str
    output_dir: Path
    no_input: bool = False
    overwrite: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class RenderResult:
    """Outcome of a render request."""

    profile: Profile
    project_path: Path
    dry_run: bool


def _context(project_name: str) -> dict[str, str]:
    return {
        "project_name": project_name,
        "package_name": project_name.replace("-", "_"),
        "author": os.environ.get("USER", "Your Name"),
        "email": os.environ.get("USER_EMAIL", "your@email.com"),
        "github_username": os.environ.get("GITHUB_USERNAME", "your_username"),
    }


def _validate_request(request: RenderRequest) -> tuple[Profile, Path]:
    if not _PROJECT_NAME.fullmatch(request.project_name):
        raise RenderError(
            "Project name must be a lowercase slug beginning with a letter and containing "
            "only letters, numbers, and hyphens."
        )
    profile = get_profile(request.profile_id)
    output_dir = request.output_dir.expanduser().resolve()
    if not output_dir.is_dir():
        raise RenderError(f"Output directory does not exist or is not a directory: {output_dir}")
    project_path = output_dir / request.project_name
    if project_path.exists() and not request.overwrite:
        raise RenderError(
            f"Output already exists: {project_path}. Re-run with --force only if overwriting is intended."
        )
    return profile, project_path


def render(request: RenderRequest) -> RenderResult:
    """Validate and render a project profile using the Cookiecutter library API."""
    profile, project_path = _validate_request(request)
    if request.dry_run:
        return RenderResult(profile=profile, project_path=project_path, dry_run=True)

    try:
        with tempfile.TemporaryDirectory(prefix="pytemplate-cookiecutter-") as state_dir:
            config_path = Path(state_dir) / "config.json"
            config_path.write_text(
                json.dumps({"replay_dir": str(Path(state_dir) / "replay")}), encoding="utf-8"
            )
            with resources.as_file(profile.template_resource) as template_path:
                cookiecutter(
                    str(template_path),
                    no_input=request.no_input,
                    extra_context=_context(request.project_name),
                    output_dir=str(request.output_dir.expanduser().resolve()),
                    overwrite_if_exists=request.overwrite,
                    config_file=str(config_path),
                )
    except CookiecutterException as error:
        raise RenderError(f"Cookiecutter could not render profile '{profile.identifier}': {error}") from error
    except OSError as error:
        raise RenderError(f"Could not write generated project: {error}") from error
    return RenderResult(profile=profile, project_path=project_path, dry_run=False)
