"""Black-box tests for the public command-line interface."""

from pathlib import Path

from typer.testing import CliRunner

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
    assert "FastAPI profile" in described.output


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


def test_create_renders_the_fastapi_profile_with_configured_database(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "create",
            "market-data-api",
            "--profile",
            "fastapi",
            "--output-dir",
            str(tmp_path),
            "--no-input",
        ],
    )

    database_module = tmp_path / "market-data-api" / "market_data_api" / "db.py"
    environment_file = tmp_path / "market-data-api" / ".env.example"
    assert result.exit_code == 0, result.output
    assert "settings.DATABASE_URL" in database_module.read_text(encoding="utf-8")
    assert "MARKET_DATA_API_DATABASE_URL" in environment_file.read_text(encoding="utf-8")
    assert not (tmp_path / "market-data-api" / ".env").exists()


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
