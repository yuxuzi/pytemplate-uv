"""Tests for the interactive component picker."""

from dataclasses import replace
from typing import Any

import pytest

from pytemplate.picker import choose_components, selectable_components
from pytemplate.profiles import bundled_catalog


def test_selectable_components_are_the_optional_ones_that_are_not_planned() -> None:
    catalog = bundled_catalog()
    profile = catalog.profile("fastapi")

    ids = {item.identifier for item in selectable_components(profile, catalog.component_map())}

    planned = {c.identifier for c in catalog.components if c.status == "planned"}
    assert ids == set(profile.optional_components) - planned
    assert not ids & set(profile.default_components)


def test_a_profile_without_optional_components_is_never_prompted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = bundled_catalog()
    profile = replace(catalog.profile("python"), optional_components=())

    def fail(*_: Any, **__: Any) -> None:
        pytest.fail("the picker prompted")

    monkeypatch.setattr("questionary.checkbox", fail)

    assert choose_components(profile, catalog.component_map()) == []
