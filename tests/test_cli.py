"""Black-box tests for the public command-line interface."""

from pathlib import Path

from typer.testing import CliRunner

from pytemplate.main import app

runner = CliRunner()


def test_help_describes_the_public_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "create" in result.output
    assert "list-profiles" in result.output
    assert "describe-profile" in result.output


def test_list_profiles_includes_the_bundled_profiles() -> None:
    result = runner.invoke(app, ["list-profiles"])

    assert result.exit_code == 0
    assert "python" in result.output
    assert "fastapi" in result.output


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


def test_create_renders_the_fastapi_profile_with_configured_database(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["create", "market-data-api", "--profile", "fastapi", "--output-dir", str(tmp_path), "--no-input"],
    )

    database_module = tmp_path / "market-data-api" / "market_data_api" / "db.py"
    assert result.exit_code == 0, result.output
    assert "settings.DATABASE_URL" in database_module.read_text(encoding="utf-8")


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
