"""Interactive choice of optional components for `pytemplate create`."""

from __future__ import annotations

from collections.abc import Mapping

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
