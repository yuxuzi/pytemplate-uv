"""Tests for the bundled agent skill and machine-readable CLI output."""

import json
import re
from pathlib import Path

import yaml
from typer.testing import CliRunner

from pytemplate.agent_skill import skill_text
from pytemplate.main import app

runner = CliRunner()


def _frontmatter(text: str) -> dict[str, str]:
    _, header, _ = text.split("---\n", 2)
    data: dict[str, str] = yaml.safe_load(header)
    return data


def test_skill_show_prints_valid_frontmatter() -> None:
    result = runner.invoke(app, ["skill", "show"])

    assert result.exit_code == 0
    frontmatter = _frontmatter(result.output)
    assert frontmatter["name"] == "pytemplate"
    assert "FastAPI" in frontmatter["description"]


def test_skill_install_writes_and_refuses_to_overwrite(tmp_path: Path) -> None:
    first = runner.invoke(app, ["skill", "install", "--dest", str(tmp_path)])
    second = runner.invoke(app, ["skill", "install", "--dest", str(tmp_path)])
    forced = runner.invoke(app, ["skill", "install", "--dest", str(tmp_path), "--force"])

    target = tmp_path / "pytemplate" / "SKILL.md"
    assert first.exit_code == 0, first.output
    assert target.read_text(encoding="utf-8") == skill_text()
    assert second.exit_code == 1
    assert "already exists" in second.output
    assert forced.exit_code == 0, forced.output


def test_skill_only_references_existing_cli_commands() -> None:
    commands = set(re.findall(r"uvx pytemplate-uv ([a-z][a-z-]+)", skill_text()))

    assert {
        "list-profiles",
        "describe-profile",
        "list-components",
        "describe-component",
        "plan",
        "create-from-config",
        "update",
    } <= commands
    for command in commands:
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0, f"{command}: {result.output}"


def test_describe_profile_json_includes_questions_and_commands() -> None:
    result = runner.invoke(app, ["describe-profile", "fastapi", "--json"])

    payload = json.loads(result.output)
    names = [question["name"] for question in payload["question_details"]]
    assert result.exit_code == 0
    assert payload["identifier"] == "fastapi"
    assert "uv run pytest" in payload["lifecycle_commands"]
    assert names[:2] == ["project_name", "package_name"]
    assert "profile" not in names


def test_list_json_outputs_parse() -> None:
    profiles = json.loads(runner.invoke(app, ["list-profiles", "--json"]).output)
    components = json.loads(runner.invoke(app, ["list-components", "--json"]).output)
    component = json.loads(runner.invoke(app, ["describe-component", "api", "--json"]).output)

    assert [profile["identifier"] for profile in profiles] == ["fastapi", "python"]
    assert {item["identifier"] for item in components} == {
        "api",
        "auth",
        "auth-api-key",
        "auth-oidc",
        "cli",
        "container",
        "database",
        "worker",
    }
    assert component["compatible_profiles"] == ["fastapi"]
