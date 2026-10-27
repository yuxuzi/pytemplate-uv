"""Discovery and metadata for bundled project profiles."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Iterable
import tomllib


class ProfileNotFoundError(ValueError):
    """Raised when a requested profile is not bundled with the package."""


@dataclass(frozen=True)
class Profile:
    """A versioned, bundled project profile."""

    identifier: str
    name: str
    description: str
    version: str
    template_directory: str
    aliases: tuple[str, ...] = ()

    @property
    def template_resource(self):
        """Return the traversable Cookiecutter template directory."""
        return resources.files("pytemplate").joinpath("templates", self.template_directory)


def _profiles() -> Iterable[Profile]:
    templates = resources.files("pytemplate").joinpath("templates")
    for entry in templates.iterdir():
        manifest = entry.joinpath("profile.toml")
        if not entry.is_dir() or not manifest.is_file():
            continue
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
        yield Profile(
            identifier=data["id"],
            name=data["name"],
            description=data["description"],
            version=data["version"],
            template_directory=entry.name,
            aliases=tuple(data.get("aliases", [])),
        )


def list_profiles() -> tuple[Profile, ...]:
    """Return all bundled profiles in stable identifier order."""
    return tuple(sorted(_profiles(), key=lambda profile: profile.identifier))


def get_profile(identifier: str) -> Profile:
    """Resolve a profile by identifier or documented compatibility alias."""
    for profile in list_profiles():
        if identifier == profile.identifier or identifier in profile.aliases:
            return profile
    available = ", ".join(profile.identifier for profile in list_profiles())
    raise ProfileNotFoundError(f"Unknown profile '{identifier}'. Available profiles: {available}.")
