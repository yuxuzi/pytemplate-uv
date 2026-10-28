"""Unit tests for profile and component metadata contracts."""

import pytest

from pytemplate.profiles import ComponentCompatibilityError, get_profile, resolve_components


def test_profiles_declare_supported_python_and_default_components() -> None:
    profile = get_profile("fastapi")

    assert profile.supported_python == ("3.11", "3.12", "3.13", "3.14")
    assert profile.default_components == ("api", "database")


def test_empty_component_selection_uses_profile_defaults() -> None:
    resolved = resolve_components(get_profile("python"), ())

    assert [component.identifier for component in resolved] == ["cli"]


def test_component_selection_rejects_duplicates() -> None:
    with pytest.raises(ComponentCompatibilityError, match="only once"):
        resolve_components(get_profile("fastapi"), ("api", "api"))


def test_component_selection_rejects_an_incompatible_component() -> None:
    with pytest.raises(ComponentCompatibilityError, match="not available"):
        resolve_components(get_profile("python"), ("database",))


def test_component_selection_cannot_omit_a_current_profile_foundation() -> None:
    with pytest.raises(ComponentCompatibilityError, match="requires these foundation components"):
        resolve_components(get_profile("fastapi"), ("api",))
