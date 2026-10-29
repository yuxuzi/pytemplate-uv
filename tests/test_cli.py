"""Black-box tests for the public command-line interface."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import pytemplate.rendering as rendering
from pytemplate.main import app, create_project_app

runner = CliRunner()


def test_help_describes_the_public_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "create" in result.output
    assert "list-profiles" in result.output
    assert "describe-profile" in result.output
    assert "list-components" in result.output
    assert "create-from-config" in result.output
    assert "validate" in result.output


def test_list_profiles_includes_the_bundled_profiles() -> None:
    result = runner.invoke(app, ["list-profiles"])

    assert result.exit_code == 0
    assert "python" in result.output
    assert "fastapi" in result.output
    assert "3.13" in result.output
    assert "3.14" in result.output


def test_component_commands_describe_the_factory_contract() -> None:
    listed = runner.invoke(app, ["list-components"])
    described = runner.invoke(app, ["describe-component", "database"])

    assert listed.exit_code == 0, listed.output
    assert "database" in listed.output
    assert described.exit_code == 0, described.output
    assert "Requires: api" in described.output
    assert "DATABASE_URL" in described.output


def test_create_dry_run_does_not_write_a_project(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["create", "market-data-api", "--output-dir", str(tmp_path), "--no-input", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert "would create" in result.output
    assert not (tmp_path / "market-data-api").exists()


def test_create_renders_the_python_profile(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["create", "market-data-api", "--output-dir", str(tmp_path), "--no-input"],
    )

    project = tmp_path / "market-data-api"
    assert result.exit_code == 0, result.output
    assert (project / "pyproject.toml").is_file()
    assert (project / "market_data_api" / "cli.py").is_file()
    manifest = (project / ".pytemplate.toml").read_text(encoding="utf-8")
    assert 'id = "python"' in manifest
    assert 'id = "cli"' in manifest


def test_create_renders_the_fastapi_profile_with_a_configured_database(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "create",
            "market-data-api",
            "--profile",
            "fastapi",
            "--component",
            "database",
            "--output-dir",
            str(tmp_path),
            "--no-input",
        ],
    )

    project = tmp_path / "market-data-api"
    container = project / "market_data_api" / "bootstrap" / "container.py"
    environment_file = project / ".env.example"
    assert result.exit_code == 0, result.output
    assert "settings.DATABASE_URL.get_secret_value()" in container.read_text(encoding="utf-8")
    assert "MARKET_DATA_API_DATABASE_URL" in environment_file.read_text(encoding="utf-8")
    assert (project / "alembic.ini").is_file()
    assert not (project / ".env").exists()


def test_default_fastapi_project_has_no_database(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["create", "svc", "--profile", "fastapi", "-o", str(tmp_path), "--no-input"]
    )

    assert result.exit_code == 0, result.output
    assert not (tmp_path / "svc" / "alembic.ini").exists()
    assert "DATABASE_URL" not in (tmp_path / "svc" / ".env.example").read_text(encoding="utf-8")


def test_create_rejects_an_existing_output_without_force(tmp_path: Path) -> None:
    (tmp_path / "market-data-api").mkdir()

    result = runner.invoke(
        app,
        ["create", "market-data-api", "--output-dir", str(tmp_path), "--no-input"],
    )

    assert result.exit_code == 1
    assert "Output already exists" in result.output


def test_create_rejects_an_invalid_project_name(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["create", "Market Data", "--output-dir", str(tmp_path), "--no-input"],
    )

    assert result.exit_code == 1
    assert "lowercase slug" in result.output


def test_create_rejects_a_component_not_supported_by_the_profile(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "create",
            "market-data-api",
            "--component",
            "database",
            "--output-dir",
            str(tmp_path),
            "--no-input",
        ],
    )

    assert result.exit_code == 1
    assert "not available for profile 'python'" in result.output


def test_validate_and_create_from_toml_config(tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text(
        'project_name = "configured-api"\nprofile = "fastapi"\ncomponents = ["api", "database"]\n',
        encoding="utf-8",
    )

    validated = runner.invoke(app, ["validate", str(config)])
    created = runner.invoke(app, ["create-from-config", str(config)])

    assert validated.exit_code == 0, validated.output
    assert "Valid" in validated.output
    assert created.exit_code == 0, created.output
    assert (tmp_path / "configured-api" / ".pytemplate.toml").is_file()


def test_create_accepts_template_data_and_describes_inputs(tmp_path: Path) -> None:
    described = runner.invoke(app, ["describe-profile", "python"])
    created = runner.invoke(
        app,
        [
            "create",
            "market-data-api",
            "--output-dir",
            str(tmp_path),
            "--no-input",
            "--data",
            "description=Factor research toolkit",
        ],
    )

    assert described.exit_code == 0, described.output
    assert "Template inputs: project_name, package_name, description" in described.output
    assert created.exit_code == 0, created.output
    readme = (tmp_path / "market-data-api" / "README.md").read_text(encoding="utf-8")
    assert "Factor research toolkit" in readme


def test_create_rejects_malformed_template_data(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["create", "market-data-api", "--output-dir", str(tmp_path), "--data", "novalue"],
    )

    assert result.exit_code == 1
    assert "KEY=VALUE" in result.output


def test_version_option_prints_the_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.startswith("pytemplate-uv ")


def test_create_project_is_a_full_alias_of_create(tmp_path: Path) -> None:
    listed = runner.invoke(app, ["--help"])
    created = runner.invoke(
        app,
        [
            "create-project",
            "market-data-api",
            "--profile",
            "fastapi",
            "--output-dir",
            str(tmp_path),
            "--no-input",
            "--data",
            "description=Alias check",
        ],
    )

    assert "create-project" in listed.output
    assert created.exit_code == 0, created.output
    readme = (tmp_path / "market-data-api" / "README.md").read_text(encoding="utf-8")
    assert "Alias check" in readme


def test_create_project_executable_runs_create_directly(tmp_path: Path) -> None:
    result = runner.invoke(
        create_project_app,
        ["market-data-api", "-p", "fastapi", "-o", str(tmp_path), "--no-input"],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "market-data-api" / "CLAUDE.md").is_file()


def test_validate_reports_components_added_by_requirements(tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text('project_name = "svc"\nprofile = "fastapi"\ncomponents = ["database"]\n')

    result = runner.invoke(app, ["validate", str(config)])

    assert result.exit_code == 0, result.output
    assert "Components: api, database" in result.output


def test_validate_rejects_auth_without_a_mode_with_guidance(tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text('project_name = "svc"\nprofile = "fastapi"\ncomponents = ["auth"]\n')

    result = runner.invoke(app, ["validate", str(config), "--json"])

    assert result.exit_code == 1
    assert "add --component auth-api-key" in json.loads(result.output)["error"]["message"]


def test_plan_json_lists_files_and_writes_nothing(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "plan",
            "--name",
            "svc",
            "--profile",
            "fastapi",
            "-c",
            "container",
            "-o",
            str(tmp_path),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0, result.output
    assert list(tmp_path.iterdir()) == []
    assert payload["ok"] is True
    assert [item["id"] for item in payload["components"]] == ["api", "container"]
    assert "Dockerfile" in payload["files"]
    assert "pyproject.toml" in payload["files"]
    assert payload["target_exists"] is False
    assert "fastapi>=0.115" in payload["dependencies"]


def test_plan_reports_an_existing_target_without_failing(tmp_path: Path) -> None:
    (tmp_path / "svc").mkdir()

    result = runner.invoke(app, ["plan", "--name", "svc", "-o", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "target exists" in result.output


def test_validate_with_options_rejects_an_incompatible_component() -> None:
    result = runner.invoke(
        app, ["validate", "--profile", "python", "--component", "database", "--json"]
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["ok"] is False
    assert payload["exit_code"] == 1
    assert payload["error"]["type"] == "ComponentCompatibilityError"
    assert "Components for 'python': cli, container" in payload["error"]["message"]


def test_validate_catches_answers_the_template_rejects() -> None:
    result = runner.invoke(app, ["validate", "--data", "python_version=3.9"])

    assert result.exit_code == 1
    assert "Copier rejected the answers" in result.output


def test_create_json_reports_the_result(tmp_path: Path) -> None:
    result = runner.invoke(app, ["create", "svc", "-o", str(tmp_path), "--no-input", "--json"])

    payload = json.loads(result.output)
    assert result.exit_code == 0, result.output
    assert payload["project_path"] == str(tmp_path.resolve() / "svc")
    assert payload["manifest_path"].endswith(".pytemplate.toml")
    assert payload["requested"] == []


def test_render_failure_exits_with_code_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(rendering, "run_copy", fail)

    result = runner.invoke(app, ["create", "svc", "-o", str(tmp_path), "--no-input", "--json"])

    assert result.exit_code == 2
    assert json.loads(result.output)["error"]["message"].endswith("disk full")


def test_bad_data_option_is_an_invalid_request() -> None:
    result = runner.invoke(app, ["validate", "--data", "novalue"])

    assert result.exit_code == 1
    assert "KEY=VALUE" in result.output
