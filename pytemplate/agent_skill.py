"""The bundled agent skill that lets Claude (or another AI tool) create projects safely."""

from __future__ import annotations

import os
import tempfile
from importlib import resources
from pathlib import Path

SKILL_NAME = "pytemplate"


class SkillInstallError(RuntimeError):
    """Raised when the skill cannot be installed."""


def skill_text() -> str:
    """Return the bundled SKILL.md content."""
    resource = resources.files("pytemplate").joinpath("skills", SKILL_NAME, "SKILL.md")
    return resource.read_text(encoding="utf-8")


# Where each kind of agent looks for skills, under the home or project directory.
AGENT_SKILL_DIRS = {
    "claude": Path(".claude") / "skills",
    "agents": Path(".agents") / "skills",
}


def default_skills_dir(*, project: bool, agent: str = "claude") -> Path:
    """Return the user-level or project-level skills directory that ``agent`` reads.

    ``claude`` is Claude Code's directory; ``agents`` is the shared ``.agents/skills``
    directory read by Codex and other Agent Skills clients.
    """
    try:
        relative = AGENT_SKILL_DIRS[agent]
    except KeyError:
        choices = ", ".join(sorted(AGENT_SKILL_DIRS))
        raise SkillInstallError(f"Unknown agent '{agent}'; choose one of: {choices}.") from None
    base = Path.cwd() if project else Path.home()
    return base / relative


def install_skill(skills_dir: Path, *, force: bool = False) -> Path:
    """Write SKILL.md to ``skills_dir/pytemplate/SKILL.md`` and return its path.

    The skill's own directory and file must not be symbolic links, so ``--force`` never writes
    through a link to a file outside ``skills_dir``. The file is replaced atomically.
    """
    skill_dir = skills_dir.expanduser() / SKILL_NAME
    target = skill_dir / "SKILL.md"
    for path in (skill_dir, target):
        if path.is_symlink():
            raise SkillInstallError(
                f"{path} is a symbolic link; remove it and install the skill again."
            )
    if target.exists() and not force:
        raise SkillInstallError(f"{target} already exists; pass --force to replace it.")
    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        _replace_file(target, skill_text())
    except OSError as error:
        raise SkillInstallError(f"Could not write {target}: {error}") from error
    return target


def _replace_file(target: Path, text: str) -> None:
    """Write ``text`` to a temporary file beside ``target`` and move it into place."""
    descriptor, staged = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        # mkstemp creates the file readable only by its owner; a skill file is not private.
        os.chmod(staged, 0o644)
        os.replace(staged, target)
    except BaseException:
        Path(staged).unlink(missing_ok=True)
        raise
