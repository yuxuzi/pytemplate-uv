"""Typed loading of deterministic render-request TOML files."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pytemplate.rendering import DEFAULT_TEMPLATE_SOURCE, RenderRequest


class ConfigurationError(ValueError):
    """Raised when a render-request configuration is malformed."""


_ALLOWED_KEYS = {
    "project_name",
    "profile",
    "output_dir",
    "components",
    "no_input",
    "overwrite",
    "data",
    "template_source",
}


def _template_data(table: object) -> dict[str, str]:
    """Validate the optional [data] table of template answers."""
    if not isinstance(table, dict) or not all(isinstance(value, str) for value in table.values()):
        raise ConfigurationError("Configuration table 'data' must map question names to strings.")
    return dict(table)


def _template_source(value: object) -> str:
    """Validate the optional git source recorded for `copier update`."""
    if not isinstance(value, str) or not value:
        raise ConfigurationError("Configuration key 'template_source' must be a non-empty string.")
    return value


def load_render_request(path: Path, *, dry_run: bool = False) -> RenderRequest:
    """Load a render request from a TOML file relative to its own directory."""
    config_path = path.expanduser().resolve()
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigurationError(f"Configuration file does not exist: {config_path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigurationError(f"Configuration file is not valid TOML: {error}") from error

    unexpected = sorted(set(data) - _ALLOWED_KEYS)
    if unexpected:
        raise ConfigurationError(f"Unsupported configuration keys: {', '.join(unexpected)}.")
    project_name = data.get("project_name")
    if not isinstance(project_name, str) or not project_name:
        raise ConfigurationError("Configuration requires a non-empty string 'project_name'.")
    profile = data.get("profile", "python")
    if not isinstance(profile, str) or not profile:
        raise ConfigurationError("Configuration key 'profile' must be a non-empty string.")
    output_value = data.get("output_dir", ".")
    if not isinstance(output_value, str):
        raise ConfigurationError("Configuration key 'output_dir' must be a string path.")
    output_dir = Path(output_value).expanduser()
    if not output_dir.is_absolute():
        output_dir = config_path.parent / output_dir
    components = data.get("components", [])
    if not isinstance(components, list) or not all(isinstance(item, str) for item in components):
        raise ConfigurationError(
            "Configuration key 'components' must be a list of component identifiers."
        )
    no_input = data.get("no_input", True)
    overwrite = data.get("overwrite", False)
    if not isinstance(no_input, bool) or not isinstance(overwrite, bool):
        raise ConfigurationError(
            "Configuration keys 'no_input' and 'overwrite' must be boolean values."
        )
    return RenderRequest(
        profile_id=profile,
        project_name=project_name,
        output_dir=output_dir,
        components=tuple(components),
        no_input=no_input,
        overwrite=overwrite,
        dry_run=dry_run,
        data=_template_data(data.get("data", {})),
        template_source=_template_source(data.get("template_source", DEFAULT_TEMPLATE_SOURCE)),
    )
