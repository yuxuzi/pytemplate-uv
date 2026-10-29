"""The published JSON Schemas stay in step with the loaders and generated files."""

import json
import tomllib
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from pytemplate import api
from pytemplate.configuration import _ALLOWED_KEYS
from pytemplate.main import app
from pytemplate.packs import _PACK_KEYS
from pytemplate.profiles import _COMPONENT_KEYS, _PROFILE_KEYS, _SETTING_KEYS
from pytemplate.schema import SCHEMAS

runner = CliRunner()


@pytest.mark.parametrize(
    ("name", "keys"),
    [
        ("profile", _PROFILE_KEYS),
        ("component", _COMPONENT_KEYS),
        ("pack", _PACK_KEYS),
        ("request", _ALLOWED_KEYS),
    ],
)
def test_schema_properties_match_the_loader(name: str, keys: frozenset[str]) -> None:
    schema = SCHEMAS[name]

    assert set(schema["properties"]) == set(keys)
    assert schema["additionalProperties"] is False
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_setting_schema_matches_the_loader() -> None:
    setting = SCHEMAS["component"]["properties"]["settings"]["items"]

    assert set(setting["properties"]) == set(_SETTING_KEYS)


def _check_object(instance: Any, schema: dict[str, Any], where: str) -> None:
    assert isinstance(instance, dict), where
    for key in schema.get("required", []):
        assert key in instance, f"{where}.{key} is required"
    extra = schema.get("additionalProperties")
    for key, value in instance.items():
        if key in schema.get("properties", {}):
            _check(value, schema["properties"][key], f"{where}.{key}")
        else:
            assert extra is not False, f"{where}.{key} is not allowed"
            if isinstance(extra, dict):
                _check(value, extra, f"{where}.{key}")


def _check_any(instance: Any, options: list[dict[str, Any]], where: str) -> None:
    errors = []
    for option in options:
        try:
            _check(instance, option, where)
            return
        except AssertionError as error:
            errors.append(str(error))
    raise AssertionError(f"{where}: {errors}")


def _check(instance: Any, schema: dict[str, Any], where: str = "$") -> None:
    """Check the subset of JSON Schema the published schemas use."""
    if "const" in schema:
        assert instance == schema["const"], where
    if "enum" in schema:
        assert instance in schema["enum"], where
    if "anyOf" in schema:
        _check_any(instance, schema["anyOf"], where)
    kind = schema.get("type")
    if kind == "object":
        _check_object(instance, schema, where)
    elif kind == "array":
        assert isinstance(instance, list), where
        for index, item in enumerate(instance):
            _check(item, schema["items"], f"{where}[{index}]")
    elif kind == "string":
        assert isinstance(instance, str), where


@pytest.mark.parametrize(
    ("profile_id", "components"), [("python", ()), ("fastapi", ("container",))]
)
def test_generated_manifest_matches_the_manifest_schema(
    profile_id: str, components: tuple[str, ...], tmp_path: Path
) -> None:
    project = api.render(
        api.RenderRequest(
            profile_id=profile_id,
            project_name="schema-check",
            output_dir=tmp_path,
            components=components,
            no_input=True,
        )
    ).project_path

    _check(tomllib.loads((project / ".pytemplate.toml").read_text("utf-8")), SCHEMAS["manifest"])


def test_bundled_manifests_match_their_schemas() -> None:
    root = Path(api.__file__).parent
    for path in (root / "components").glob("*.toml"):
        _check(tomllib.loads(path.read_text("utf-8")), SCHEMAS["component"], path.name)
    for path in (root / "templates").glob("*/profile.toml"):
        _check(tomllib.loads(path.read_text("utf-8")), SCHEMAS["profile"], str(path))


def test_schema_command_prints_valid_json() -> None:
    result = runner.invoke(app, ["schema", "request"])

    assert result.exit_code == 0
    assert json.loads(result.output)["title"].startswith("pytemplate-uv render request")


def test_schema_command_rejects_unknown_names() -> None:
    result = runner.invoke(app, ["schema", "nope"])

    assert result.exit_code == 1
    assert "Unknown schema 'nope'" in result.output


def test_api_exports_resolve() -> None:
    for name in api.__all__:
        assert hasattr(api, name), name
