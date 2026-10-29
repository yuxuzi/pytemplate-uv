"""Unit tests for deterministic component resolution."""

from dataclasses import replace

import pytest

from pytemplate.profiles import (
    Component,
    ComponentCompatibilityError,
    ComponentNotFoundError,
    ManifestError,
    Setting,
    get_component,
    get_profile,
)
from pytemplate.resolution import resolve


def _demo(identifier: str, **overrides: object) -> Component:
    fields: dict[str, object] = {
        "identifier": identifier,
        "name": identifier.title(),
        "description": f"The {identifier} component.",
        "version": "1",
        "status": "stable",
        "compatible_profiles": ("demo",),
        **overrides,
    }
    return Component(**fields)  # type: ignore[arg-type]


DEMO_PROFILE = replace(
    get_profile("python"),
    identifier="demo",
    default_components=("base",),
    optional_components=("auth", "cache", "metrics", "queue", "redis", "store"),
    dependencies=("typer>=0.12",),
    dependency_groups={"dev": ("ruff>=0.6",)},
    lifecycle_commands=("uv run pytest",),
)
CATALOG = {
    component.identifier: component
    for component in (
        _demo("base", dependencies=("rich>=13.7",), paths=("{package}/base.py",)),
        _demo("store", dependencies=("sqlalchemy>=2.0",), paths=("{package}/store.py",)),
        _demo(
            "cache",
            requires=("store",),
            dependency_groups={"dev": ("fakeredis>=2",), "redis": ("redis>=5",)},
            lifecycle_commands=("uv run cache-check",),
        ),
        _demo("queue", requires=("cache",), conflicts=("metrics",)),
        _demo("metrics", security_notes=("Metrics may expose request paths.",)),
        _demo("redis", status="planned"),
        _demo("auth", requires_any=("cache", "metrics")),
    )
}


def test_profile_defaults_are_always_included() -> None:
    resolution = resolve(DEMO_PROFILE, (), CATALOG)

    assert resolution.component_ids == ("base",)
    assert resolution.requested == ()
    assert resolution.added == ()


def test_requires_are_added_transitively_and_reported() -> None:
    resolution = resolve(DEMO_PROFILE, ("queue",), CATALOG)

    assert resolution.component_ids == ("base", "cache", "queue", "store")
    assert resolution.requested == ("queue",)
    assert resolution.added == ("cache", "store")


def test_resolution_does_not_depend_on_request_order() -> None:
    first = resolve(DEMO_PROFILE, ("cache", "metrics"), CATALOG)
    second = resolve(DEMO_PROFILE, ("metrics", "cache"), CATALOG)

    assert first == second


def test_dependencies_groups_paths_and_commands_are_merged() -> None:
    resolution = resolve(DEMO_PROFILE, ("cache", "metrics"), CATALOG)

    assert resolution.dependencies == ("rich>=13.7", "sqlalchemy>=2.0", "typer>=0.12")
    assert resolution.dependency_groups == {
        "dev": ("fakeredis>=2", "ruff>=0.6"),
        "redis": ("redis>=5",),
    }
    assert resolution.paths == ("{package}/base.py", "{package}/store.py")
    assert resolution.lifecycle_commands == ("uv run pytest", "uv run cache-check")
    assert resolution.security_notes == ("Metrics may expose request paths.",)


def test_conflicting_components_fail_with_both_names() -> None:
    with pytest.raises(ComponentCompatibilityError, match="'metrics' and 'queue' cannot be"):
        resolve(DEMO_PROFILE, ("queue", "metrics"), CATALOG)


def test_conflicts_are_detected_from_either_side() -> None:
    catalog = {**CATALOG, "metrics": replace(CATALOG["metrics"], conflicts=("store",))}

    with pytest.raises(ComponentCompatibilityError, match="'metrics' and 'store'"):
        resolve(DEMO_PROFILE, ("metrics", "store"), catalog)


def test_duplicate_selection_names_the_repeated_component() -> None:
    with pytest.raises(ComponentCompatibilityError, match="remove the repeated cache"):
        resolve(DEMO_PROFILE, ("cache", "cache"), CATALOG)


def test_unknown_component_lists_the_catalog() -> None:
    with pytest.raises(ComponentNotFoundError, match="Unknown component 'nope'. Available"):
        resolve(DEMO_PROFILE, ("nope",), CATALOG)


def test_component_not_offered_by_the_profile_lists_alternatives() -> None:
    profile = replace(DEMO_PROFILE, optional_components=("metrics",))

    with pytest.raises(
        ComponentCompatibilityError,
        match=r"'cache' is not available for profile 'demo'\. Components for 'demo': base, metrics",
    ):
        resolve(profile, ("cache",), CATALOG)


def test_missing_requirement_names_the_component_that_needs_it() -> None:
    profile = replace(DEMO_PROFILE, optional_components=("cache",))

    with pytest.raises(
        ComponentCompatibilityError, match=r"'store' \(required by 'cache'\) is not available"
    ):
        resolve(profile, ("cache",), CATALOG)


def test_planned_components_cannot_be_selected() -> None:
    with pytest.raises(ComponentCompatibilityError, match="'redis' is planned"):
        resolve(DEMO_PROFILE, ("redis",), CATALOG)


def test_settings_declared_differently_by_two_components_are_a_manifest_error() -> None:
    setting = Setting(name="URL", type="str", description="A URL.")
    catalog = {
        **CATALOG,
        "store": replace(CATALOG["store"], settings=(setting,)),
        "metrics": replace(CATALOG["metrics"], settings=(replace(setting, secret=True),)),
    }

    with pytest.raises(ManifestError, match="declare setting 'URL' differently"):
        resolve(DEMO_PROFILE, ("metrics", "store"), catalog)


def test_bundled_fastapi_default_needs_no_infrastructure() -> None:
    resolution = resolve(get_profile("fastapi"))

    assert resolution.component_ids == ("api",)
    assert "fastapi>=0.115" in resolution.dependencies
    assert not any("sqlalchemy" in spec for spec in resolution.dependencies)
    assert "DATABASE_URL" not in [setting.name for setting in resolution.settings]


def test_bundled_auth_mode_pulls_in_the_auth_foundation() -> None:
    resolution = resolve(get_profile("fastapi"), ("auth-oidc", "database"))

    assert resolution.component_ids == ("api", "auth", "auth-oidc", "database")
    assert resolution.added == ("auth",)
    assert "pyjwt[crypto]>=2.10" in resolution.dependencies
    assert resolution.dependency_groups["postgres"] == ("asyncpg>=0.30",)
    assert "uv run alembic upgrade head" in resolution.lifecycle_commands
    assert get_component("database").requires == ("api",)


def test_bundled_python_profile_rejects_a_service_component() -> None:
    with pytest.raises(ComponentCompatibilityError, match="'database' is not available"):
        resolve(get_profile("python"), ("database",))


def test_bundled_auth_without_a_mode_suggests_one() -> None:
    with pytest.raises(ComponentCompatibilityError, match="add --component auth-api-key"):
        resolve(get_profile("fastapi"), ("auth",))


def test_bundled_auth_modes_conflict() -> None:
    with pytest.raises(ComponentCompatibilityError, match="'auth-api-key' and 'auth-oidc'"):
        resolve(get_profile("fastapi"), ("auth-api-key", "auth-oidc"))


def test_requires_any_needs_one_of_the_options_and_suggests_the_first() -> None:
    with pytest.raises(
        ComponentCompatibilityError,
        match=r"'auth' needs one of: cache, metrics; add --component cache\.",
    ):
        resolve(DEMO_PROFILE, ("auth",), CATALOG)


def test_requires_any_is_satisfied_by_any_option() -> None:
    assert resolve(DEMO_PROFILE, ("auth", "metrics"), CATALOG).component_ids == (
        "auth",
        "base",
        "metrics",
    )
