"""Interactive choice of optional components for `pytemplate create`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pytemplate.errors import RequestError
from pytemplate.profiles import Component, Profile


class PickerCancelledError(RequestError):
    """Raised when the user abandons the component picker."""


def selectable_components(profile: Profile, components: Mapping[str, Component]) -> list[Component]:
    """Return the profile's optional components that can be selected today."""
    return [
        components[identifier]
        for identifier in profile.optional_components
        if identifier in components and components[identifier].status != "planned"
    ]


def choose_components(profile: Profile, components: Mapping[str, Component]) -> list[str]:
    """Ask which optional components to add; return no choices when the profile has none.

    Resolution still adds required components and refuses conflicting ones afterwards.
    """
    options = selectable_components(profile, components)
    if not options:
        return []
    import questionary  # imported here: only an interactive create needs it

    answer = questionary.checkbox(
        f"Optional components for '{profile.identifier}' (space selects, enter confirms)",
        choices=[
            questionary.Choice(f"{item.identifier} - {item.description}", value=item.identifier)
            for item in options
        ],
    ).ask()
    if answer is None:
        raise PickerCancelledError("Cancelled; nothing was created.")
    return [str(identifier) for identifier in answer]


def choose_profile(profiles: Sequence[Profile], checks: Mapping[str, str] | None = None) -> str:
    """Ask which profile to create; ``python`` is listed first when there is one.

    ``checks`` maps a profile to its lifecycle result on a hub entry (``passed`` or ``not-run``),
    shown beside it. Ctrl-C raises ``PickerCancelledError``.
    """
    import questionary  # imported here: only an interactive create needs it

    checks = checks or {}
    ordered = sorted(profiles, key=lambda profile: profile.identifier != "python")
    choices = [
        questionary.Choice(
            f"{profile.identifier} - {profile.description}{_check_label(checks, profile)}",
            value=profile.identifier,
        )
        for profile in ordered
    ]
    answer = questionary.select("Project profile", choices=choices).ask()
    if answer is None:
        raise PickerCancelledError("Cancelled; nothing was created.")
    return str(answer)


def _check_label(checks: Mapping[str, str], profile: Profile) -> str:
    if profile.identifier not in checks:
        return ""
    return " (checks passed)" if checks[profile.identifier] == "passed" else " (checks not run)"
