"""Typed loading of deterministic render-request TOML files."""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path

from pytemplate.errors import RequestError
from pytemplate.hub import HubPin, pin_for
from pytemplate.packs import is_git_source
from pytemplate.rendering import RenderRequest


class ConfigurationError(RequestError, ValueError):
    """Raised when a render-request configuration is malformed."""


_ALLOWED_KEYS = {
    "project_name",
    "profile",
    "output_dir",
    "components",
    "no_input",
    "overwrite",
    "data",
    "template",
    "template_ref",
    "template_commit",
    "template_digest",
    "hub",
}


def _template_data(table: object) -> dict[str, str]:
    """Validate the optional [data] table of template answers."""
    if not isinstance(table, dict) or not all(isinstance(value, str) for value in table.values()):
        raise ConfigurationError("Configuration table 'data' must map question names to strings.")
    return dict(table)


def _optional_string(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"Configuration key '{key}' must be a non-empty string.")
    return value


def _template(data: dict[str, object], base: Path) -> str | None:
    """Return the optional pack source; relative pack directories resolve against ``base``."""
    template = _optional_string(data, "template")
    if template is None or is_git_source(template):
        return template
    path = Path(template).expanduser()
    return str(path if path.is_absolute() else base / path)


def _hub_pins(
    data: dict[str, object], base: Path, notify: Callable[[str], None] | None
) -> tuple[HubPin | None, tuple[str | None, str | None, str | None, str | None]]:
    """Return the pack pins of a request: from ``hub`` when it is set, else as written."""
    template = _template(data, base)
    template_ref = _optional_string(data, "template_ref")
    template_commit = _optional_string(data, "template_commit")
    template_digest = _optional_string(data, "template_digest")
    hub = _optional_string(data, "hub")
    if hub is None:
        return None, (template, template_ref, template_commit, template_digest)
    pin = pin_for(
        hub,
        template=template,
        template_ref=template_ref,
        template_commit=template_commit,
        template_digest=template_digest,
    )
    if notify is not None:
        notify(pin.notice)
    return pin, (pin.location, pin.tag, pin.commit, pin.digest)


def load_render_request(
    path: Path,
    *,
    dry_run: bool = False,
    notify: Callable[[str], None] | None = None,
) -> RenderRequest:
    """Load a render request from a TOML file relative to its own directory.

    ``hub = "owner/pack@tag"`` resolves the pins through pytemplate-hub, as ``--hub`` does; the
    resolution is announced through ``notify`` when one is given.
    """
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
    pin, pins = _hub_pins(data, config_path.parent, notify)
    template, template_ref, template_commit, template_digest = pins
    return RenderRequest(
        profile_id=profile,
        project_name=project_name,
        output_dir=output_dir,
        components=tuple(components),
        no_input=no_input,
        overwrite=overwrite,
        dry_run=dry_run,
        data=_template_data(data.get("data", {})),
        template=template,
        template_ref=template_ref,
        template_commit=template_commit,
        template_digest=template_digest,
        hub=pin.pack if pin is not None else None,
    )
