"""The bundled agent skill that lets Claude (or another AI tool) create projects safely."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

SKILL_NAME = "pytemplate"


class SkillInstallError(RuntimeError):
    """Raised when the skill cannot be installed."""


def skill_text() -> str:
    """Return the bundled SKILL.md content."""
    resource = resources.files("pytemplate").joinpath("skills", SKILL_NAME, "SKILL.md")
    return resource.read_text(encoding="utf-8")


def default_skills_dir(*, project: bool) -> Path:
    """Return Claude Code's user-level or project-level skills directory."""
    base = Path.cwd() if project else Path.home()
    return base / ".claude" / "skills"


def install_skill(skills_dir: Path, *, force: bool = False) -> Path:
    """Write SKILL.md to ``skills_dir/pytemplate/SKILL.md`` and return its path."""
    target = skills_dir.expanduser() / SKILL_NAME / "SKILL.md"
    if target.exists() and not force:
        raise SkillInstallError(f"{target} already exists; pass --force to replace it.")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(skill_text(), encoding="utf-8")
    except OSError as error:
        raise SkillInstallError(f"Could not write {target}: {error}") from error
    return target
