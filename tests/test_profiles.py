"""Unit tests for profile and component metadata contracts."""

from dataclasses import replace

import pytest

from pytemplate.profiles import (
    ManifestError,
    Setting,
    _parse_component,
    _parse_profile,
    bundled_catalog,
    check_catalog,
    get_component,
    get_profile,
    list_components,
    list_profiles,
)


def test_profiles_declare_supported_python_and_default_components() -> None:
    profile = get_profile("fastapi")

    assert profile.supported_python == ("3.11", "3.12", "3.13", "3.14", "3.15")
    assert profile.default_components == ("api",)


def test_bundled_catalog_satisfies_the_contract() -> None:
    check_catalog()

    fastapi = get_profile("fastapi")
    assert (fastapi.kind, fastapi.status, fastapi.contract) == ("service", "stable", 1)
    assert fastapi.optional_components == (
        "auth",
        "auth-api-key",
        "auth-oidc",
        "container",
        "database",
        "worker",
    )
    assert fastapi.legacy_components == ("container", "database")
    assert get_component("auth").requires_any == ("auth-api-key", "auth-oidc")
    assert get_component("auth-oidc").conflicts == ("auth-api-key",)
    assert get_component("database").settings[0] == Setting(
        name="DATABASE_URL",
        type="str",
        description="SQLAlchemy async URL, for example postgresql+asyncpg://user@host/db.",
        required_in_production=True,
        secret=True,
    )


def _component(**overrides: object) -> dict[str, object]:
    return {
        "contract": 1,
        "id": "demo",
        "name": "Demo",
        "description": "A demo component.",
        "version": "1",
        "status": "stable",
        "compatible_profiles": ["python"],
        **overrides,
    }


def test_component_manifest_rejects_unknown_keys_with_the_file_name() -> None:
    with pytest.raises(ManifestError, match=r"components/demo.toml: unknown key\(s\) fragments"):
        _parse_component("components/demo.toml", _component(fragments=["x"]))


def test_component_manifest_requires_the_supported_contract() -> None:
    with pytest.raises(ManifestError, match="'contract' must be 1"):
        _parse_component("components/demo.toml", _component(contract=2))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"status": "beta"}, "'status' must be one of stable, experimental, planned"),
        ({"id": "Demo_1"}, "'id' must be a lowercase slug"),
        ({"requires": "api"}, "'requires' must be a list of strings"),
        ({"paths": ["a", "a"]}, "'paths' must be a list without duplicates"),
        ({"dependency_groups": {"dev": "ruff"}}, "'dependency_groups' must be a table"),
        ({"requires": ["demo"]}, "cannot require or conflict with itself"),
        ({"requires": ["api"], "conflicts": ["api"]}, "both require and conflict"),
        ({"settings": [{"name": "X", "type": "float", "description": "x"}]}, "'type' must be"),
        (
            {"settings": [{"name": "X", "type": "str", "description": "x", "secret": "yes"}]},
            r"\[settings\]\[0\]: key 'secret' must be a boolean",
        ),
    ],
)
def test_component_manifest_rejects_malformed_values(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ManifestError, match=message):
        _parse_component("components/demo.toml", _component(**overrides))


def test_profile_manifest_rejects_questions_missing_from_questions_yml() -> None:
    data = {
        "contract": 1,
        "id": "demo",
        "name": "Demo",
        "description": "A demo profile.",
        "version": "1",
        "kind": "library",
        "status": "stable",
        "questions": ["colour"],
    }

    with pytest.raises(ManifestError, match="questions colour are not defined"):
        _parse_profile("templates/demo/profile.toml", "demo", data, ("description",))


def test_catalog_rejects_unknown_component_references() -> None:
    broken = replace(get_component("database"), requires=("cache",))
    components = tuple(
        broken if component.identifier == "database" else component
        for component in list_components()
    )

    with pytest.raises(ManifestError, match="'requires' names unknown cache"):
        check_catalog(replace(bundled_catalog(), components=components))


def test_catalog_rejects_a_compatible_component_the_profile_does_not_list() -> None:
    fastapi = replace(
        get_profile("fastapi"),
        optional_components=("auth", "auth-api-key", "auth-oidc", "container", "database"),
    )
    profiles = tuple(
        fastapi if profile.identifier == "fastapi" else profile for profile in list_profiles()
    )

    with pytest.raises(ManifestError, match="compatible component 'worker' must be listed"):
        check_catalog(replace(bundled_catalog(), profiles=profiles))


def test_catalog_requires_component_question_choices_to_match_the_components() -> None:
    questions = {**bundled_catalog().questions, "components": {"choices": ["api"]}}

    with pytest.raises(ManifestError, match="choices are exactly the catalog's components"):
        check_catalog(replace(bundled_catalog(), questions=questions))
