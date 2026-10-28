"""End-to-end checks that generated projects pass their own quality gates.

These tests install dependencies with ``uv sync`` and therefore need network access and the
``uv`` executable. They run only when ``PYTEMPLATE_SMOKE=1`` is set (CI sets it).
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from pytemplate.profiles import get_profile
from pytemplate.rendering import RenderRequest, render

pytestmark = pytest.mark.skipif(
    os.environ.get("PYTEMPLATE_SMOKE") != "1" or shutil.which("uv") is None,
    reason="set PYTEMPLATE_SMOKE=1 (and install uv) to run generated-project smoke tests",
)

# A long name catches templated lines that only fit the line-length limit for short names.
PROJECT_NAME = "quantitative-research-market-data-service"


@pytest.mark.parametrize("profile_id", ["python", "fastapi"])
def test_generated_project_passes_its_lifecycle_commands(profile_id: str, tmp_path: Path) -> None:
    project = render(
        RenderRequest(
            profile_id=profile_id,
            project_name=PROJECT_NAME,
            output_dir=tmp_path,
            no_input=True,
        )
    ).project_path
    package = PROJECT_NAME.replace("-", "_")
    environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}

    for command in get_profile(profile_id).lifecycle_commands:
        completed = subprocess.run(
            command.format(package=package).split(),
            cwd=project,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (
            f"{command!r} failed in {profile_id}:\n{completed.stdout}\n{completed.stderr}"
        )
