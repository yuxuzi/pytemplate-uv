"""Shared fixtures."""

import os
from pathlib import Path
from textwrap import dedent

import pytest

# Rich wraps CLI output to the terminal width, so a phrase can split wherever a long temporary
# path happens to end. Render wide so text assertions never depend on the machine. This runs
# before any test module imports the CLI, whose console reads COLUMNS when it is created.
os.environ["COLUMNS"] = "1000"

ANSWERS_TEMPLATE = "{{ _copier_answers|to_nice_yaml -}}\n"


def write_pack(root: Path) -> Path:
    """Write a minimal, valid template pack with one profile and one optional component."""
    files = {
        "pytemplate-pack.toml": """
            contract = 1
            id = "demo-pack"
            name = "Demo pack"
            description = "A pack used by the tests."
            version = "1.0.0"
        """,
        "copier.yml": """
            _subdirectory: "{{ profile }}/template"
            _templates_suffix: .jinja
            --- !include questions.yml
        """,
        "questions.yml": """
            profile:
              type: str
              choices: [tool]
            project_name:
              type: str
            package_name:
              type: str
              default: "{{ project_name | replace('-', '_') }}"
            description:
              type: str
              default: A demo tool
            components:
              type: str
              multiselect: true
              choices: [extra]
              default: []
        """,
        "tool/profile.toml": """
            contract = 1
            id = "tool"
            name = "Demo tool"
            description = "A tool package."
            version = "1"
            kind = "library"
            status = "experimental"
            optional_components = ["extra"]
            dependencies = ["pydantic>=2"]
            questions = ["description"]
        """,
        "components/extra.toml": """
            contract = 1
            id = "extra"
            name = "Extra"
            description = "An extra module."
            version = "1"
            status = "stable"
            compatible_profiles = ["tool"]
            dependencies = ["rich>=13.7"]
            paths = ["{package}/extra.py"]
        """,
        "tool/template/README.md.jinja": "# {{ project_name }}\n\n{{ description }}\n",
        "tool/template/{{ package_name }}/__init__.py": "",
        "tool/template/{{ package_name }}/extra.py": "VALUE = 1\n",
        "tool/template/{{ _copier_conf.answers_file }}.jinja": ANSWERS_TEMPLATE,
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = content if name.endswith(".jinja") and "answers" in name else dedent(content)
        path.write_text(text.lstrip("\n"), encoding="utf-8")
    return root


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    """Return a minimal local template pack directory."""
    return write_pack(tmp_path / "pack")
