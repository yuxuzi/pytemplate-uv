"""Composition contract: rendered files and dependencies follow the component manifests.

These tests are what make "adding a component needs no CLI or renderer change" hold: every
component's owned paths appear exactly when it is selected, and the generated pyproject
declares exactly the dependencies the manifests resolve to.
"""

import tomllib
from itertools import combinations
from pathlib import Path

import pytest
import yaml

from pytemplate.profiles import bundled_catalog
from pytemplate.rendering import RenderRequest, render
from pytemplate.resolution import Resolution, matches, resolve

CATALOG = bundled_catalog()
PACKAGE = "market_data_api"


def _selections() -> list[tuple[str, tuple[str, ...]]]:
    """Return one request per distinct resolved component set of every profile."""
    cases: dict[tuple[str, tuple[str, ...]], tuple[str, tuple[str, ...]]] = {}
    components = CATALOG.component_map()
    for profile in CATALOG.profiles:
        optional = [
            identifier
            for identifier in profile.optional_components
            if components[identifier].status != "planned"
        ]
        for size in range(len(optional) + 1):
            for chosen in combinations(optional, size):
                try:
                    resolved = resolve(profile, chosen).component_ids
                except ValueError:
                    continue  # invalid selections are covered by the resolution tests
                cases.setdefault((profile.identifier, resolved), (profile.identifier, chosen))
    return sorted(cases.values())


SELECTIONS = _selections()


_RENDERED: dict[tuple[str, tuple[str, ...]], tuple[Path, Resolution]] = {}


def _render(tmp_path: Path, profile_id: str, chosen: tuple[str, ...]) -> tuple[Path, Resolution]:
    """Render each selection once per session; the checks below only read the output."""
    key = (profile_id, chosen)
    if key not in _RENDERED:
        output = tmp_path / "render"
        output.mkdir()
        result = render(
            RenderRequest(
                profile_id=profile_id,
                project_name="market-data-api",
                output_dir=output,
                components=chosen,
                no_input=True,
            )
        )
        _RENDERED[key] = (result.project_path, result.resolution)
    return _RENDERED[key]


def _files(project: Path) -> list[str]:
    return sorted(
        path.relative_to(project).as_posix() for path in project.rglob("*") if path.is_file()
    )


@pytest.mark.parametrize(("profile_id", "chosen"), SELECTIONS, ids=str)
def test_component_paths_render_only_when_selected(
    profile_id: str, chosen: tuple[str, ...], tmp_path: Path
) -> None:
    project, resolution = _render(tmp_path, profile_id, chosen)
    files = _files(project)
    selected = set(resolution.component_ids)

    for component in CATALOG.components:
        if profile_id not in component.compatible_profiles:
            continue
        owned = [name for name in files if any(matches(p, name, PACKAGE) for p in component.paths)]
        if component.identifier in selected:
            for pattern in component.paths:
                assert any(matches(pattern, name, PACKAGE) for name in files), (
                    f"{component.identifier}: '{pattern}' matched no rendered file"
                )
        else:
            assert owned == [], f"{component.identifier} is not selected but rendered {owned}"


@pytest.mark.parametrize(("profile_id", "chosen"), SELECTIONS, ids=str)
def test_each_file_has_at_most_one_owning_component(
    profile_id: str, chosen: tuple[str, ...], tmp_path: Path
) -> None:
    project, resolution = _render(tmp_path, profile_id, chosen)

    for name in _files(project):
        owners = [
            component.identifier
            for component in resolution.components
            if any(matches(pattern, name, PACKAGE) for pattern in component.paths)
        ]
        assert len(owners) <= 1, f"{name} is owned by {owners}"


@pytest.mark.parametrize(("profile_id", "chosen"), SELECTIONS, ids=str)
def test_pyproject_declares_exactly_the_resolved_dependencies(
    profile_id: str, chosen: tuple[str, ...], tmp_path: Path
) -> None:
    project, resolution = _render(tmp_path, profile_id, chosen)
    pyproject = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))

    assert sorted(pyproject["project"]["dependencies"]) == sorted(resolution.dependencies)
    assert {group: sorted(specs) for group, specs in pyproject["dependency-groups"].items()} == {
        group: sorted(specs) for group, specs in resolution.dependency_groups.items()
    }


@pytest.mark.parametrize(("profile_id", "chosen"), SELECTIONS, ids=str)
def test_answers_and_manifest_record_the_resolution(
    profile_id: str, chosen: tuple[str, ...], tmp_path: Path
) -> None:
    project, resolution = _render(tmp_path, profile_id, chosen)
    answers = yaml.safe_load((project / ".copier-answers.yml").read_text(encoding="utf-8"))
    manifest = tomllib.loads((project / ".pytemplate.toml").read_text(encoding="utf-8"))

    assert answers["components"] == list(resolution.component_ids)
    assert [entry["id"] for entry in manifest["components"]] == list(resolution.component_ids)
    owners = {entry["path"]: entry["owner"] for entry in manifest["files"]}
    assert set(owners.values()) <= {"profile", *resolution.component_ids}


def test_every_profile_combination_is_covered() -> None:
    assert ("python", ("container",)) in SELECTIONS
    assert ("fastapi", ()) in SELECTIONS
    resolved = {tuple(resolve(CATALOG.profile(p), c).component_ids) for p, c in SELECTIONS}
    assert ("api", "auth", "auth-oidc", "container", "database", "worker") in resolved


@pytest.mark.parametrize(("profile_id", "chosen"), SELECTIONS, ids=str)
def test_env_example_documents_every_resolved_setting(
    profile_id: str, chosen: tuple[str, ...], tmp_path: Path
) -> None:
    project, resolution = _render(tmp_path, profile_id, chosen)
    example = project / ".env.example"
    if not example.is_file():
        assert resolution.settings == ()
        return

    text = example.read_text(encoding="utf-8")
    for setting in resolution.settings:
        assert f"{PACKAGE.upper()}_{setting.name}=" in text, setting.name


@pytest.mark.parametrize(("profile_id", "chosen"), SELECTIONS, ids=str)
def test_application_code_has_no_hard_coded_database_url(
    profile_id: str, chosen: tuple[str, ...], tmp_path: Path
) -> None:
    project, _ = _render(tmp_path, profile_id, chosen)

    for path in (project / PACKAGE).rglob("*.py"):
        if path.name != "settings.py":
            assert "sqlite" not in path.read_text(encoding="utf-8"), path
