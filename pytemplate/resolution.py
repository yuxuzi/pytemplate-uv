"""Deterministic resolution of a profile plus requested components into one render plan."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache
from itertools import combinations

from pytemplate.profiles import (
    Component,
    ComponentCompatibilityError,
    ComponentNotFoundError,
    ManifestError,
    Profile,
    Setting,
    list_components,
)


@dataclass(frozen=True)
class Resolution:
    """The fully resolved, order-independent result of one component selection.

    ``requested`` keeps the caller's explicit choices and ``added`` the components pulled in
    by ``requires``, so later update tooling can explain why each component is present.
    """

    profile: Profile
    components: tuple[Component, ...]
    requested: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    dependency_groups: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    paths: tuple[str, ...] = ()
    # Paths owned by this profile's unselected components; rendering leaves them out.
    excluded_paths: tuple[str, ...] = ()
    settings: tuple[Setting, ...] = ()
    lifecycle_commands: tuple[str, ...] = ()
    security_notes: tuple[str, ...] = ()

    def exclude_patterns(self, package: str) -> list[str]:
        """Return Copier `exclude` patterns (rendered paths) for the unselected components."""
        return [pattern.replace("{package}", package) for pattern in self.excluded_paths]

    @property
    def component_ids(self) -> tuple[str, ...]:
        """Return the identifiers of every resolved component, in resolution order."""
        return tuple(component.identifier for component in self.components)

    def owner(self, path: str, package: str) -> str:
        """Return the component that owns a rendered POSIX ``path``, or ``"profile"``."""
        for component in self.components:
            if any(matches(pattern, path, package) for pattern in component.paths):
                return component.identifier
        return "profile"


@cache
def _pattern(pattern: str) -> re.Pattern[str]:
    """Compile a manifest glob: ``**`` spans directories, ``*`` and ``?`` stay within one."""
    parts = re.split(r"(\*\*/?|\*|\?)", pattern)
    regex = "".join(
        ".*"
        if part.startswith("**")
        else "[^/]*"
        if part == "*"
        else "[^/]"
        if part == "?"
        else re.escape(part)
        for part in parts
    )
    return re.compile(regex)


def matches(pattern: str, path: str, package: str) -> bool:
    """Return whether a rendered ``path`` matches a component ``paths`` glob.

    ``{package}`` in the pattern stands for the project's import package name.
    """
    return _pattern(pattern.replace("{package}", package)).fullmatch(path) is not None


def _available(profile: Profile) -> str:
    return ", ".join(profile.components) or "none"


def _selectable(
    profile: Profile, catalog: Mapping[str, Component], identifier: str, reason: str
) -> Component:
    """Return a component the profile offers and that can be selected now."""
    component = catalog.get(identifier)
    if component is None:
        raise ComponentNotFoundError(
            f"Unknown component '{identifier}'. Available components: {', '.join(sorted(catalog))}."
        )
    if identifier not in profile.components:
        raise ComponentCompatibilityError(
            f"Component '{identifier}' {reason}is not available for profile "
            f"'{profile.identifier}'. Components for '{profile.identifier}': "
            f"{_available(profile)}."
        )
    if component.status == "planned":
        raise ComponentCompatibilityError(
            f"Component '{identifier}' {reason}is planned and cannot be selected yet; "
            f"run `pytemplate describe-component {identifier}` for its status."
        )
    return component


def _requirements(groups: Iterable[Iterable[str]]) -> tuple[str, ...]:
    """Merge requirement lists, dropping exact duplicates, sorted case-insensitively."""
    merged = {spec for specs in groups for spec in specs}
    return tuple(sorted(merged, key=lambda spec: (spec.lower(), spec)))


def _merged_settings(components: tuple[Component, ...]) -> tuple[Setting, ...]:
    owners: dict[str, tuple[str, Setting]] = {}
    for component in components:
        for setting in component.settings:
            previous = owners.get(setting.name)
            if previous is not None and previous[1] != setting:
                raise ManifestError(
                    f"Components '{previous[0]}' and '{component.identifier}' declare setting "
                    f"'{setting.name}' differently; one component must own it."
                )
            owners.setdefault(setting.name, (component.identifier, setting))
    return tuple(setting for _, setting in sorted(owners.values(), key=lambda o: o[1].name))


def _unique(items: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def _add_requirements(
    profile: Profile, catalog: Mapping[str, Component], selected: dict[str, Component]
) -> set[str]:
    """Add every transitively required component to ``selected``; return the added ones."""
    pending = sorted(selected)
    added: set[str] = set()
    while pending:
        owner = selected[pending.pop(0)]
        for needed in owner.requires:
            if needed not in selected:
                selected[needed] = _selectable(
                    profile, catalog, needed, f"(required by '{owner.identifier}') "
                )
                added.add(needed)
                pending.append(needed)
    return added


def _check_constraints(selected: Mapping[str, Component]) -> None:
    """Reject unmet ``requires_any`` and any ``conflicts`` between selected components."""
    for identifier in sorted(selected):
        options = selected[identifier].requires_any
        if options and not set(options) & set(selected):
            raise ComponentCompatibilityError(
                f"Component '{identifier}' needs one of: {', '.join(options)}; "
                f"add --component {options[0]}."
            )
    for first, second in combinations(sorted(selected), 2):
        if second in selected[first].conflicts or first in selected[second].conflicts:
            raise ComponentCompatibilityError(
                f"Components '{first}' and '{second}' cannot be combined; "
                "select at most one of them."
            )


def resolve(
    profile: Profile,
    requested: tuple[str, ...] = (),
    catalog: Mapping[str, Component] | None = None,
) -> Resolution:
    """Resolve the profile defaults plus ``requested`` components, or raise an actionable error.

    The result depends only on the set of requested identifiers, never on their order:
    ``requires`` are added transitively, ``conflicts`` are rejected, and components are
    ordered by identifier. ``catalog`` defaults to the bundled components.
    """
    if catalog is None:
        catalog = {component.identifier: component for component in list_components()}
    if len(requested) != len(set(requested)):
        duplicates = sorted({item for item in requested if requested.count(item) > 1})
        raise ComponentCompatibilityError(
            f"A component may be selected only once; remove the repeated {', '.join(duplicates)}."
        )

    selected = {
        identifier: _selectable(profile, catalog, identifier, "")
        for identifier in sorted(set(profile.default_components) | set(requested))
    }
    added = _add_requirements(profile, catalog, selected)
    _check_constraints(selected)

    components = tuple(selected[identifier] for identifier in sorted(selected))
    groups: dict[str, list[str]] = {
        group: list(specs) for group, specs in profile.dependency_groups.items()
    }
    for component in components:
        for group, specs in component.dependency_groups.items():
            groups.setdefault(group, []).extend(specs)
    return Resolution(
        profile=profile,
        components=components,
        requested=tuple(sorted(set(requested))),
        added=tuple(sorted(added)),
        dependencies=_requirements(
            [profile.dependencies, *(component.dependencies for component in components)]
        ),
        dependency_groups={
            group: _requirements([specs]) for group, specs in sorted(groups.items())
        },
        paths=_unique(path for component in components for path in component.paths),
        excluded_paths=_unique(
            path
            for identifier in profile.components
            if identifier not in selected and identifier in catalog
            for path in catalog[identifier].paths
        ),
        settings=_merged_settings(components),
        lifecycle_commands=_unique(
            [
                *profile.lifecycle_commands,
                *(command for component in components for command in component.lifecycle_commands),
            ]
        ),
        security_notes=_unique(
            note for component in components for note in component.security_notes
        ),
    )
