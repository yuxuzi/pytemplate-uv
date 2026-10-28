"""Discovery, compatibility checks, and metadata for bundled factory capabilities."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Any

import yaml


class ProfileNotFoundError(ValueError):
    """Raised when a requested profile is not bundled with the package."""


class ComponentNotFoundError(ValueError):
    """Raised when a requested component is not bundled with the package."""


class ComponentCompatibilityError(ValueError):
    """Raised when a component cannot be used with the selected profile."""


@dataclass(frozen=True)
class Component:
    """A versioned, optional capability that a profile can expose."""

    identifier: str
    name: str
    description: str
    version: str
    compatible_profiles: tuple[str, ...]
    dependency_groups: tuple[str, ...] = ()
    template_fragments: tuple[str, ...] = ()
    configuration_schema: str | None = None


@dataclass(frozen=True)
class Profile:
    """A versioned, bundled project profile."""

    identifier: str
    name: str
    description: str
    version: str
    template_directory: str
    aliases: tuple[str, ...] = ()
    supported_python: tuple[str, ...] = ("3.11", "3.12", "3.13", "3.14")
    components: tuple[str, ...] = ()
    default_components: tuple[str, ...] = ()
    configuration_schema: str = "questions.yml"
    lifecycle_commands: tuple[str, ...] = ()
    security_posture: str = "No external services are contacted while rendering."
    questions: tuple[str, ...] = ()

    @property
    def template_resource(self) -> Traversable:
        """Return the shared Copier template root; the `profile` answer selects the subtree."""
        return templates_root()


def templates_root() -> Traversable:
    """Return the bundled Copier template root containing copier.yml and questions.yml."""
    return resources.files("pytemplate").joinpath("templates")


def _read_manifest(resource: Traversable) -> dict[str, Any]:
    return tomllib.loads(resource.read_text(encoding="utf-8"))


def _strings(data: dict[str, Any], key: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Return a manifest list of strings, rejecting malformed bundled metadata early."""
    value = data.get(key, list(default))
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"Manifest key '{key}' must be a list of strings, got {value!r}.")
    return tuple(value)


@cache
def _question_specs() -> dict[str, dict[str, Any]]:
    """Return the shared Copier questions in declaration order, excluding settings."""
    data = yaml.safe_load(templates_root().joinpath("questions.yml").read_text(encoding="utf-8"))
    return {
        str(name): dict(spec or {})
        for name, spec in (data or {}).items()
        if not str(name).startswith("_")
    }


def question_details() -> list[dict[str, Any]]:
    """Describe the user-answerable template questions for humans and AI agents."""
    return [
        {
            "name": name,
            "help": spec.get("help"),
            "default": spec.get("default"),
            "choices": spec.get("choices"),
        }
        for name, spec in _question_specs().items()
        if name != "profile"
    ]


@cache
def _profiles() -> tuple[Profile, ...]:
    templates = templates_root()
    questions = tuple(question["name"] for question in question_details())
    profiles: list[Profile] = []
    for entry in templates.iterdir():
        manifest = entry.joinpath("profile.toml")
        if not entry.is_dir() or not manifest.is_file():
            continue
        data = _read_manifest(manifest)
        profiles.append(
            Profile(
                identifier=str(data["id"]),
                name=str(data["name"]),
                description=str(data["description"]),
                version=str(data["version"]),
                template_directory=entry.name,
                aliases=_strings(data, "aliases"),
                supported_python=_strings(
                    data, "supported_python", ("3.11", "3.12", "3.13", "3.14")
                ),
                components=_strings(data, "components"),
                default_components=_strings(data, "default_components"),
                configuration_schema=str(data.get("configuration_schema", "questions.yml")),
                lifecycle_commands=_strings(data, "lifecycle_commands"),
                security_posture=str(
                    data.get(
                        "security_posture", "No external services are contacted while rendering."
                    )
                ),
                questions=questions,
            )
        )
    return tuple(sorted(profiles, key=lambda profile: profile.identifier))


@cache
def _components() -> tuple[Component, ...]:
    component_root = resources.files("pytemplate").joinpath("components")
    components: list[Component] = []
    for entry in component_root.iterdir():
        if not entry.name.endswith(".toml") or not entry.is_file():
            continue
        data = _read_manifest(entry)
        components.append(
            Component(
                identifier=str(data["id"]),
                name=str(data["name"]),
                description=str(data["description"]),
                version=str(data["version"]),
                compatible_profiles=_strings(data, "compatible_profiles"),
                dependency_groups=_strings(data, "dependency_groups"),
                template_fragments=_strings(data, "template_fragments"),
                configuration_schema=(
                    str(data["configuration_schema"]) if "configuration_schema" in data else None
                ),
            )
        )
    return tuple(sorted(components, key=lambda component: component.identifier))


def list_profiles() -> tuple[Profile, ...]:
    """Return all bundled profiles in stable identifier order."""
    return _profiles()


def get_profile(identifier: str) -> Profile:
    """Resolve a profile by identifier or documented compatibility alias."""
    for profile in list_profiles():
        if identifier == profile.identifier or identifier in profile.aliases:
            return profile
    available = ", ".join(profile.identifier for profile in list_profiles())
    raise ProfileNotFoundError(f"Unknown profile '{identifier}'. Available profiles: {available}.")


def list_components() -> tuple[Component, ...]:
    """Return all bundled components in stable identifier order."""
    return _components()


def get_component(identifier: str) -> Component:
    """Resolve a component by its stable identifier."""
    for component in list_components():
        if component.identifier == identifier:
            return component
    available = ", ".join(component.identifier for component in list_components())
    raise ComponentNotFoundError(
        f"Unknown component '{identifier}'. Available components: {available}."
    )


def resolve_components(profile: Profile, requested: tuple[str, ...]) -> tuple[Component, ...]:
    """Resolve and validate requested components for one profile."""
    identifiers = requested or profile.default_components
    if len(identifiers) != len(set(identifiers)):
        raise ComponentCompatibilityError("A component may be selected only once.")

    resolved = tuple(get_component(identifier) for identifier in identifiers)
    for component in resolved:
        if component.identifier not in profile.components:
            raise ComponentCompatibilityError(
                f"Component '{component.identifier}' is not available "
                f"for profile '{profile.identifier}'."
            )
        if profile.identifier not in component.compatible_profiles:
            raise ComponentCompatibilityError(
                f"Component '{component.identifier}' does not support "
                f"profile '{profile.identifier}'."
            )
    required = set(profile.default_components)
    if set(identifiers) != required:
        required_names = ", ".join(profile.default_components) or "none"
        raise ComponentCompatibilityError(
            f"Profile '{profile.identifier}' currently requires these foundation components: "
            f"{required_names}."
        )
    return resolved
