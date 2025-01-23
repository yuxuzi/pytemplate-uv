"""Pytest configuration and fixtures for pytemplate-uv."""
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_project_dir() -> str:
    """Create a temporary directory for project creation.

    Returns:
        str: Path to the temporary directory
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        yield tmpdir
        os.chdir(original_cwd)


@pytest.fixture
def project_templates_path() -> Path:
    """Get the path to project templates.

    Returns:
        Path: Path to the templates directory
    """
    return Path(__file__).parent.parent / "templates"
