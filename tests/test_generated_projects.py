"""End-to-end checks that generated projects pass their own quality gates.

Every distinct component set of every stable profile is rendered and its resolved lifecycle
commands are run (sync, lint, format, strict type-check, tests, and component commands such as
`alembic upgrade head`). These tests install dependencies with ``uv sync`` and therefore need
network access and the ``uv`` executable. They run only when ``PYTEMPLATE_SMOKE=1`` is set (CI
sets it). ``PYTEMPLATE_SMOKE_PROFILE`` limits them to one profile, and
``PYTEMPLATE_SMOKE_PYTHON`` sets the generated projects' minimum ``python_version`` (CI uses the
job's interpreter, so the newest job checks ruff's and mypy's rules for the newest target).
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from test_composition import SELECTIONS  # tests/ is on sys.path (rootdir conftest)

from pytemplate.rendering import RenderRequest, render

pytestmark = pytest.mark.skipif(
    os.environ.get("PYTEMPLATE_SMOKE") != "1" or shutil.which("uv") is None,
    reason="set PYTEMPLATE_SMOKE=1 (and install uv) to run generated-project smoke tests",
)

# A long name catches templated lines that only fit the line-length limit for short names.
PROJECT_NAME = "quantitative-research-market-data-service"
ONLY_PROFILE = os.environ.get("PYTEMPLATE_SMOKE_PROFILE")
TARGET_PYTHON = os.environ.get("PYTEMPLATE_SMOKE_PYTHON")


@pytest.mark.parametrize(
    ("profile_id", "chosen"),
    [case for case in SELECTIONS if ONLY_PROFILE in (None, case[0])],
    ids=lambda value: value if isinstance(value, str) else "+".join(value) or "default",
)
def test_generated_project_passes_its_lifecycle_commands(
    profile_id: str, chosen: tuple[str, ...], tmp_path: Path
) -> None:
    result = render(
        RenderRequest(
            profile_id=profile_id,
            project_name=PROJECT_NAME,
            output_dir=tmp_path,
            components=chosen,
            no_input=True,
            data={"python_version": TARGET_PYTHON} if TARGET_PYTHON else {},
        )
    )
    package = PROJECT_NAME.replace("-", "_")
    environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}

    for command in result.resolution.lifecycle_commands:
        completed = subprocess.run(
            command.format(package=package).split(),
            cwd=result.project_path,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (
            f"{command!r} failed for {profile_id} {chosen}:\n{completed.stdout}\n{completed.stderr}"
        )
