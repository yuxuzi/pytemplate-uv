"""Tests for the pytemplate-uv CLI."""
from __future__ import annotations

import logging
from pathlib import Path

import typer
from typer.testing import CliRunner

from cli import app

runner = CliRunner()
logger = logging.getLogger(__name__)

def test_fastapi_command(temp_project_dir: str, project_templates_path: str) -> None:
    """Test the FastAPI project creation command.

    Args:
        temp_project_dir (str): Temporary directory for project creation
        project_templates_path (str): Path to project templates

    """
    logger.info("Starting FastAPI project creation test")

    result = runner.invoke(
        app,
        [
            "create-project",
            "--template",
            "fastapi",
            "--project-name",
            "test-fastapi-project"
        ],
    )

    assert result.exit_code == 0, f"Command failed with output: {result.output}"
    assert "Creating new project using fastapi template..." in result.output

def test_help_command() -> None:
    """Test the help command provides useful information."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Create Python projects from templates using uv package manager" in result.output
    assert "--template" in result.output

    logger.info("Help command test completed successfully")
