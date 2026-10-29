"""Strict loading of factory-contract (version 1) catalogs: profiles, components, questions."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Any

import yaml

CONTRACT_VERSION = 1
PROFILE_KINDS = ("library", "cli", "service")
PROFILE_STATUSES = ("stable", "experimental")
# A planned component is described for discovery but cannot be selected yet.
COMPONENT_STATUSES = ("stable", "experimental", "planned")
SETTING_TYPES = ("str", "int", "bool", "list")
DEFAULT_PYTHON = ("3.11", "3.12", "3.13", "3.14", "3.15")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]*$")
# Questions answered by pytemplate itself from the request, never through --data.
RESERVED_QUESTIONS = ("profile", "components")


class ManifestError(ValueError):
    """Raised when a profile or component manifest violates the factory contract."""


class ProfileNotFoundError(ValueError):
    """Raised when a requested profile is not bundled with the package."""


class ComponentNotFoundError(ValueError):
    """Raised when a requested component is not bundled with the package."""


class ComponentCompatibilityError(ValueError):
    """Raised when a component cannot be used with the selected profile."""


@dataclass(frozen=True)
class Setting:
    """An environment setting a component reads at runtime; never a stored value."""

    name: str
    type: str
    description: str
    required_in_production: bool = False
    secret: bool = False


@dataclass(frozen=True)
class Component:
    """A versioned, optional capability that compatible profiles can include."""

    identifier: str
    name: str
    description: str
    version: str
    status: str
    compatible_profiles: tuple[str, ...]
    requires: tuple[str, ...] = ()
    # At least one of these must also be selected (for example, one authentication mode).
    requires_any: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    dependency_groups: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    paths: tuple[str, ...] = ()
    settings: tuple[Setting, ...] = ()
    questions: tuple[str, ...] = ()
    lifecycle_commands: tuple[str, ...] = ()
    security_notes: tuple[str, ...] = ()
    contract: int = CONTRACT_VERSION


@dataclass(frozen=True)
class Profile:
    """A versioned project profile: the application shape that components extend."""

    identifier: str
    name: str
    description: str
    version: str
    kind: str
    status: str
    template_directory: str
    aliases: tuple[str, ...] = ()
    supported_python: tuple[str, ...] = DEFAULT_PYTHON
    default_components: tuple[str, ...] = ()
    optional_components: tuple[str, ...] = ()
    # Components implied for projects generated before `components` was recorded (2.x).
    legacy_components: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    dependency_groups: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    lifecycle_commands: tuple[str, ...] = ()
    security_posture: str = "No external services are contacted while rendering."
    questions: tuple[str, ...] = ()
    contract: int = CONTRACT_VERSION

    @property
    def components(self) -> tuple[str, ...]:
        """Return every component this profile can include, defaults first."""
        return self.default_components + self.optional_components


class _Manifest:
    """Typed, strict access to one TOML manifest; every error names the file."""

    def __init__(
        self,
        label: str,
        data: dict[str, Any],
        allowed: frozenset[str],
        *,
        top_level: bool = True,
    ) -> None:
        self.label = label
        self.data = data
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ManifestError(
                f"{label}: unknown key(s) {', '.join(unknown)}. "
                f"Allowed keys: {', '.join(sorted(allowed))}."
            )
        contract = data.get("contract")
        if top_level and contract != CONTRACT_VERSION:
            raise ManifestError(
                f"{label}: 'contract' must be {CONTRACT_VERSION}, got {contract!r}. "
                "This pytemplate-uv release reads factory contract version "
                f"{CONTRACT_VERSION} only."
            )

    def error(self, key: str, expected: str) -> ManifestError:
        return ManifestError(
            f"{self.label}: key '{key}' must be {expected}, got {self.data.get(key)!r}."
        )

    def string(self, key: str, default: str | None = None) -> str:
        value = self.data.get(key, default)
        if not isinstance(value, str) or not value.strip():
            raise self.error(key, "a non-empty string")
        return value

    def identifier(self, key: str = "id") -> str:
        value = self.string(key)
        if not _IDENTIFIER.fullmatch(value):
            raise self.error(key, "a lowercase slug such as 'market-data'")
        return value

    def choice(self, key: str, choices: tuple[str, ...], default: str | None = None) -> str:
        value = self.string(key, default)
        if value not in choices:
            raise self.error(key, f"one of {', '.join(choices)}")
        return value

    def strings(self, key: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
        value = self.data.get(key, list(default))
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise self.error(key, "a list of strings")
        if len(value) != len(set(value)):
            raise self.error(key, "a list without duplicates")
        return tuple(value)

    def groups(self, key: str) -> dict[str, tuple[str, ...]]:
        value = self.data.get(key, {})
        if not isinstance(value, dict) or not all(
            isinstance(specs, list) and all(isinstance(spec, str) for spec in specs)
            for specs in value.values()
        ):
            raise self.error(key, "a table mapping group names to lists of requirement strings")
        return {str(group): tuple(specs) for group, specs in sorted(value.items())}

    def settings(self, key: str) -> tuple[Setting, ...]:
        value = self.data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise self.error(key, "an array of tables")
        settings: list[Setting] = []
        for index, item in enumerate(value):
            entry = _Manifest(
                f"{self.label} [{key}][{index}]",
                item,
                _SETTING_KEYS,
                top_level=False,
            )
            flags = {
                flag: entry.data.get(flag, False) for flag in ("required_in_production", "secret")
            }
            for flag, flag_value in flags.items():
                if not isinstance(flag_value, bool):
                    raise entry.error(flag, "a boolean")
            settings.append(
                Setting(
                    name=entry.string("name"),
                    type=entry.choice("type", SETTING_TYPES),
                    description=entry.string("description"),
                    **flags,
                )
            )
        return tuple(settings)


_SETTING_KEYS = frozenset({"name", "type", "description", "required_in_production", "secret"})
_PROFILE_KEYS = frozenset(
    {
        "contract",
        "id",
        "name",
        "description",
        "version",
        "kind",
        "status",
        "aliases",
        "supported_python",
        "default_components",
        "optional_components",
        "dependencies",
        "dependency_groups",
        "questions",
        "legacy_components",
        "lifecycle_commands",
        "security_posture",
    }
)
_COMPONENT_KEYS = frozenset(
    {
        "contract",
        "id",
        "name",
        "description",
        "version",
        "status",
        "compatible_profiles",
        "requires",
        "requires_any",
        "conflicts",
        "dependencies",
        "dependency_groups",
        "paths",
        "settings",
        "questions",
        "lifecycle_commands",
        "security_notes",
    }
)


def _read_manifest(label: str, resource: Traversable) -> dict[str, Any]:
    try:
        return tomllib.loads(resource.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ManifestError(f"{label}: not valid TOML: {error}") from error


def _question_specs(label: str, resource: Traversable) -> dict[str, dict[str, Any]]:
    """Return Copier questions in declaration order, excluding `_` settings."""
    if not resource.is_file():
        raise ManifestError(f"{label}: questions.yml is missing.")
    try:
        data = yaml.safe_load(resource.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ManifestError(f"{label}: questions.yml is not valid YAML: {error}") from error
    if data is not None and not isinstance(data, dict):
        raise ManifestError(f"{label}: questions.yml must be a mapping of questions.")
    return {
        str(name): dict(spec or {})
        for name, spec in (data or {}).items()
        if not str(name).startswith("_")
    }


def _parse_profile(
    label: str, directory: str, data: dict[str, Any], available: tuple[str, ...]
) -> Profile:
    manifest = _Manifest(label, data, _PROFILE_KEYS)
    questions = manifest.strings("questions", available)
    unknown = sorted(set(questions) - set(available))
    if unknown:
        raise ManifestError(
            f"{label}: questions {', '.join(unknown)} are not defined in questions.yml."
        )
    supported_python = manifest.strings("supported_python", DEFAULT_PYTHON)
    if not set(supported_python) <= set(DEFAULT_PYTHON):
        raise manifest.error("supported_python", f"a subset of {', '.join(DEFAULT_PYTHON)}")
    default_components = manifest.strings("default_components")
    optional_components = manifest.strings("optional_components")
    overlap = sorted(set(default_components) & set(optional_components))
    if overlap:
        raise ManifestError(
            f"{label}: components {', '.join(overlap)} are both default and optional."
        )
    return Profile(
        identifier=manifest.identifier(),
        name=manifest.string("name"),
        description=manifest.string("description"),
        version=manifest.string("version"),
        kind=manifest.choice("kind", PROFILE_KINDS),
        status=manifest.choice("status", PROFILE_STATUSES),
        template_directory=directory,
        aliases=manifest.strings("aliases"),
        supported_python=supported_python,
        default_components=default_components,
        optional_components=optional_components,
        legacy_components=manifest.strings("legacy_components"),
        dependencies=manifest.strings("dependencies"),
        dependency_groups=manifest.groups("dependency_groups"),
        lifecycle_commands=manifest.strings("lifecycle_commands"),
        security_posture=manifest.string(
            "security_posture", "No external services are contacted while rendering."
        ),
        # Answers every profile needs, even if the manifest lists a narrower set.
        questions=tuple(dict.fromkeys(("project_name", "package_name", *questions))),
    )


def _parse_component(
    label: str, data: dict[str, Any], available: tuple[str, ...] | None = None
) -> Component:
    manifest = _Manifest(label, data, _COMPONENT_KEYS)
    identifier = manifest.identifier()
    requires = manifest.strings("requires")
    conflicts = manifest.strings("conflicts")
    if identifier in requires or identifier in conflicts:
        raise ManifestError(f"{label}: a component cannot require or conflict with itself.")
    if set(requires) & set(conflicts):
        raise ManifestError(f"{label}: a component cannot both require and conflict with another.")
    questions = manifest.strings("questions")
    unknown = sorted(set(questions) - set(available if available is not None else questions))
    if unknown:
        raise ManifestError(
            f"{label}: questions {', '.join(unknown)} are not defined in questions.yml."
        )
    return Component(
        identifier=identifier,
        name=manifest.string("name"),
        description=manifest.string("description"),
        version=manifest.string("version"),
        status=manifest.choice("status", COMPONENT_STATUSES),
        compatible_profiles=manifest.strings("compatible_profiles"),
        requires=requires,
        requires_any=manifest.strings("requires_any"),
        conflicts=conflicts,
        dependencies=manifest.strings("dependencies"),
        dependency_groups=manifest.groups("dependency_groups"),
        paths=manifest.strings("paths"),
        settings=manifest.settings("settings"),
        questions=questions,
        lifecycle_commands=manifest.strings("lifecycle_commands"),
        security_notes=manifest.strings("security_notes"),
    )


def _check_component_references(components: tuple[Component, ...], profile_ids: set[str]) -> None:
    component_ids = {component.identifier for component in components}
    for component in components:
        label = f"components/{component.identifier}.toml"
        for key, references, known in (
            ("compatible_profiles", component.compatible_profiles, profile_ids),
            ("requires", component.requires, component_ids),
            ("requires_any", component.requires_any, component_ids),
            ("conflicts", component.conflicts, component_ids),
        ):
            missing = sorted(set(references) - known)
            if missing:
                raise ManifestError(f"{label}: '{key}' names unknown {', '.join(missing)}.")


def _check_profile_components(profile: Profile, components: tuple[Component, ...]) -> None:
    label = f"{profile.template_directory}/profile.toml"
    by_id = {component.identifier: component for component in components}
    for identifier in profile.components:
        listed = by_id.get(identifier)
        if listed is None:
            raise ManifestError(f"{label}: unknown component '{identifier}'.")
        if profile.identifier not in listed.compatible_profiles:
            raise ManifestError(
                f"{label}: component '{identifier}' does not list "
                f"'{profile.identifier}' in compatible_profiles."
            )
        if identifier in profile.default_components and listed.status == "planned":
            raise ManifestError(f"{label}: default component '{identifier}' is still planned.")
    unknown_legacy = sorted(set(profile.legacy_components) - set(profile.components))
    if unknown_legacy:
        raise ManifestError(
            f"{label}: legacy_components {', '.join(unknown_legacy)} are not profile components."
        )
    for component in components:
        if (
            profile.identifier in component.compatible_profiles
            and component.identifier not in profile.components
        ):
            raise ManifestError(
                f"{label}: compatible component '{component.identifier}' must be listed in "
                "default_components or optional_components."
            )


def _check_component_choices(
    components: tuple[Component, ...], questions: Mapping[str, Mapping[str, Any]]
) -> None:
    choices = questions.get("components", {}).get("choices")
    expected = sorted(component.identifier for component in components)
    if sorted(choices or []) != expected:
        raise ManifestError(
            "questions.yml: the 'components' question must be a multiselect whose choices are "
            f"exactly the catalog's components ({', '.join(expected) or 'none'})."
        )


def check_catalog(catalog: Catalog | None = None) -> None:
    """Check cross-references between a catalog's profiles, components, and questions."""
    catalog = bundled_catalog() if catalog is None else catalog
    profile_ids = {profile.identifier for profile in catalog.profiles}
    _check_component_references(catalog.components, profile_ids)
    for profile in catalog.profiles:
        _check_profile_components(profile, catalog.components)
    _check_component_choices(catalog.components, catalog.questions)


@dataclass(frozen=True)
class Catalog:
    """Profiles, components, and questions loaded from one template root."""

    root: Traversable
    profiles: tuple[Profile, ...]
    components: tuple[Component, ...]
    questions: Mapping[str, Mapping[str, Any]]

    def profile(self, identifier: str) -> Profile:
        """Resolve a profile by identifier or documented compatibility alias."""
        for profile in self.profiles:
            if identifier == profile.identifier or identifier in profile.aliases:
                return profile
        available = ", ".join(profile.identifier for profile in self.profiles)
        raise ProfileNotFoundError(
            f"Unknown profile '{identifier}'. Available profiles: {available}."
        )

    def component(self, identifier: str) -> Component:
        """Resolve a component by its stable identifier."""
        for component in self.components:
            if component.identifier == identifier:
                return component
        available = ", ".join(component.identifier for component in self.components)
        raise ComponentNotFoundError(
            f"Unknown component '{identifier}'. Available components: {available}."
        )

    def component_map(self) -> dict[str, Component]:
        """Return components keyed by identifier."""
        return {component.identifier: component for component in self.components}

    def question_details(self) -> list[dict[str, Any]]:
        """Describe the user-answerable template questions for humans and AI agents."""
        return [
            {
                "name": name,
                "help": spec.get("help"),
                "default": spec.get("default"),
                "choices": spec.get("choices"),
            }
            for name, spec in self.questions.items()
            if name not in RESERVED_QUESTIONS
        ]


def load_catalog(root: Traversable, components_root: Traversable) -> Catalog:
    """Load and cross-check a catalog.

    ``root`` holds questions.yml and one directory per profile, and ``components_root`` holds
    ``<id>.toml`` component manifests.
    """
    questions = _question_specs(str(root), root.joinpath("questions.yml"))
    available = tuple(name for name in questions if name not in RESERVED_QUESTIONS)
    profiles: list[Profile] = []
    for entry in root.iterdir():
        manifest = entry.joinpath("profile.toml")
        if not entry.is_dir() or not manifest.is_file():
            continue
        label = f"{entry.name}/profile.toml"
        profiles.append(
            _parse_profile(label, entry.name, _read_manifest(label, manifest), available)
        )
    components: list[Component] = []
    if components_root.is_dir():
        for entry in components_root.iterdir():
            if not entry.name.endswith(".toml") or not entry.is_file():
                continue
            label = f"components/{entry.name}"
            component = _parse_component(label, _read_manifest(label, entry), available)
            if f"{component.identifier}.toml" != entry.name:
                raise ManifestError(f"{label}: file name must match id '{component.identifier}'.")
            components.append(component)
    catalog = Catalog(
        root=root,
        profiles=tuple(sorted(profiles, key=lambda profile: profile.identifier)),
        components=tuple(sorted(components, key=lambda component: component.identifier)),
        questions=questions,
    )
    if not catalog.profiles:
        raise ManifestError(f"{root}: no profile directories with a profile.toml were found.")
    check_catalog(catalog)
    return catalog


@cache
def bundled_catalog() -> Catalog:
    """Return the catalog shipped inside this package."""
    package = resources.files("pytemplate")
    return load_catalog(package.joinpath("templates"), package.joinpath("components"))


def question_details() -> list[dict[str, Any]]:
    """Describe the bundled template questions for humans and AI agents."""
    return bundled_catalog().question_details()


def list_profiles() -> tuple[Profile, ...]:
    """Return all bundled profiles in stable identifier order."""
    return bundled_catalog().profiles


def get_profile(identifier: str) -> Profile:
    """Resolve a bundled profile by identifier or documented compatibility alias."""
    return bundled_catalog().profile(identifier)


def list_components() -> tuple[Component, ...]:
    """Return all bundled components in stable identifier order."""
    return bundled_catalog().components


def get_component(identifier: str) -> Component:
    """Resolve a bundled component by its stable identifier."""
    return bundled_catalog().component(identifier)
