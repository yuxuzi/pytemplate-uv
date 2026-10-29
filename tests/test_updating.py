"""Tests for `copier update` support, using a local git repository as the template source."""

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml
from copier import Settings, run_copy

from pytemplate.profiles import get_profile
from pytemplate.rendering import RenderRequest, generator_version, render
from pytemplate.resolution import resolve
from pytemplate.updating import UpdateError, UpdateRequest, update

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is required")

REPO_ROOT = Path(__file__).parent.parent
NEW_README_LINE = "Updated by template v99."


@pytest.fixture(autouse=True)
def _git_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    for prefix in ("GIT_AUTHOR", "GIT_COMMITTER"):
        monkeypatch.setenv(f"{prefix}_NAME", "Test")
        monkeypatch.setenv(f"{prefix}_EMAIL", "test@example.com")


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def _commit_all(cwd: Path, message: str) -> None:
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "-q", "-m", message)


@pytest.fixture
def template_source(tmp_path: Path) -> Path:
    """Create a git copy of the templates, tagged with the installed version."""
    source = tmp_path / "template-source"
    shutil.copytree(
        REPO_ROOT / "pytemplate" / "templates",
        source / "pytemplate" / "templates",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copytree(
        REPO_ROOT / "pytemplate" / "components",
        source / "pytemplate" / "components",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copy2(REPO_ROOT / "copier.yml", source / "copier.yml")
    _git(source, "init", "-q")
    _commit_all(source, "templates")
    _git(source, "tag", f"v{generator_version()}")
    return source


@pytest.fixture
def project(tmp_path: Path, template_source: Path) -> Path:
    """Generate and commit a project from the fixture source."""
    output = tmp_path / "projects"
    output.mkdir()
    path = render(
        RenderRequest(
            profile_id="python",
            project_name="demo-app",
            output_dir=output,
            no_input=True,
            template_source=str(template_source),
        )
    ).project_path
    _git(path, "init", "-q")
    _commit_all(path, "generated")
    return path


def _release_new_template(source: Path) -> None:
    readme = source / "pytemplate" / "templates" / "python" / "template" / "README.md.jinja"
    readme.write_text(readme.read_text(encoding="utf-8") + f"\n{NEW_README_LINE}\n", "utf-8")
    _commit_all(source, "new template")
    _git(source, "tag", "v99.0.0")


def test_answers_file_records_the_template_source(project: Path, template_source: Path) -> None:
    answers = yaml.safe_load((project / ".copier-answers.yml").read_text(encoding="utf-8"))

    assert answers["_src_path"] == str(template_source)
    assert answers["_commit"] == f"v{generator_version()}"
    assert answers["profile"] == "python"


def test_dry_run_changes_nothing(project: Path, template_source: Path) -> None:
    _release_new_template(template_source)

    result = update(UpdateRequest(project, to_ref="v99.0.0"))

    assert result.applied is False
    assert _git(project, "status", "--porcelain") == ""
    assert NEW_README_LINE not in (project / "README.md").read_text(encoding="utf-8")


def test_apply_merges_template_changes_and_keeps_user_edits(
    project: Path, template_source: Path
) -> None:
    core = project / "demo_app" / "core.py"
    core.write_text(core.read_text(encoding="utf-8") + "\nUSER_CONSTANT = 42\n", "utf-8")
    _commit_all(project, "user edit")
    _release_new_template(template_source)

    result = update(UpdateRequest(project, to_ref="v99.0.0", apply=True))

    answers = yaml.safe_load((project / ".copier-answers.yml").read_text(encoding="utf-8"))
    manifest = (project / ".pytemplate.toml").read_text(encoding="utf-8")
    assert result.from_ref == f"v{generator_version()}"
    assert NEW_README_LINE in (project / "README.md").read_text(encoding="utf-8")
    assert "USER_CONSTANT = 42" in core.read_text(encoding="utf-8")
    assert answers["_commit"] == "v99.0.0"
    assert ".git/" not in manifest


def test_update_refuses_a_dirty_tree(project: Path) -> None:
    (project / "scratch.txt").write_text("uncommitted", encoding="utf-8")

    with pytest.raises(UpdateError, match="uncommitted changes"):
        update(UpdateRequest(project, to_ref="v99.0.0"))


def test_update_requires_an_answers_file(tmp_path: Path) -> None:
    with pytest.raises(UpdateError, match="3.0 or later"):
        update(UpdateRequest(tmp_path, to_ref="v99.0.0"))


def test_update_requires_git(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)

    with pytest.raises(UpdateError, match="git is required"):
        update(UpdateRequest(project, to_ref="v99.0.0"))


def test_apply_merges_edits_to_the_same_file(project: Path, template_source: Path) -> None:
    readme = project / "README.md"
    readme.write_text("User introduction.\n\n" + readme.read_text(encoding="utf-8"), "utf-8")
    _commit_all(project, "user edits README")
    _release_new_template(template_source)

    update(UpdateRequest(project, to_ref="v99.0.0", apply=True))

    merged = readme.read_text(encoding="utf-8")
    assert merged.startswith("User introduction.")
    assert NEW_README_LINE in merged
    assert "<<<<<<<" not in merged


@pytest.mark.parametrize("profile_id", ["python", "fastapi"])
def test_git_entry_point_renders_the_same_files_as_the_bundled_one(
    profile_id: str, tmp_path: Path, template_source: Path
) -> None:
    bundled = render(
        RenderRequest(
            profile_id=profile_id,
            project_name="demo-app",
            output_dir=tmp_path,
            no_input=True,
            template_source=str(template_source),
        )
    ).project_path
    from_git = tmp_path / "from-git"
    resolution = resolve(get_profile(profile_id))
    run_copy(
        str(template_source),
        from_git,
        data={
            "profile": profile_id,
            "project_name": "demo-app",
            "components": list(resolution.component_ids),
        },
        exclude=resolution.exclude_patterns("demo_app"),
        vcs_ref=f"v{generator_version()}",
        defaults=True,
        quiet=True,
        settings=Settings(),
    )

    def tree(root: Path) -> dict[str, bytes]:
        skipped = {".copier-answers.yml", ".pytemplate.toml"}
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file() and path.name not in skipped
        }

    assert tree(bundled) == tree(from_git)


def test_no_template_file_is_ignored_by_git() -> None:
    """A git-ignored template file would be missing from release tags and `copier update`."""
    files = [
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "pytemplate" / "templates").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", *files],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert ignored.stdout == ""


def test_update_keeps_the_components_of_a_project_generated_before_3_0(
    tmp_path: Path, template_source: Path
) -> None:
    # A 2.1 development build always rendered a Dockerfile but recorded no components.
    output = tmp_path / "legacy"
    output.mkdir()
    project = render(
        RenderRequest(
            profile_id="python",
            project_name="demo-app",
            output_dir=output,
            components=("container",),
            no_input=True,
            template_source=str(template_source),
        )
    ).project_path
    _git(project, "init", "-q")
    answers_path = project / ".copier-answers.yml"
    answers = yaml.safe_load(answers_path.read_text(encoding="utf-8"))
    del answers["components"]
    answers_path.write_text(yaml.safe_dump(answers), encoding="utf-8")
    manifest_path = project / ".pytemplate.toml"
    manifest_path.write_text(
        '[generator]\nname = "pytemplate-uv"\nversion = "2.1.0"\n\n'
        '[profile]\nid = "python"\nversion = "2"\nsupported_python = ["3.11"]\n\n'
        '[[components]]\nid = "cli"\nversion = "1"\n',
        encoding="utf-8",
    )
    _commit_all(project, "2.x project")
    _release_new_template(template_source)

    update(UpdateRequest(project, to_ref="v99.0.0", apply=True))

    updated = yaml.safe_load(answers_path.read_text(encoding="utf-8"))
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    assert updated["components"] == ["cli", "container"]
    assert (project / "Dockerfile").is_file()
    assert manifest["schema"] == 2
    assert [entry["id"] for entry in manifest["components"]] == ["cli", "container"]
    assert manifest["template"] == {
        "kind": "bundled",
        "source": str(template_source),
        "ref": "v99.0.0",
    }


def test_update_does_not_add_files_of_unselected_components(
    project: Path, template_source: Path
) -> None:
    _release_new_template(template_source)

    update(UpdateRequest(project, to_ref="v99.0.0", apply=True))

    assert NEW_README_LINE in (project / "README.md").read_text(encoding="utf-8")
    assert not (project / "Dockerfile").exists()
    assert not (project / ".dockerignore").exists()


def test_update_uses_the_component_paths_of_the_target_release(
    project: Path, template_source: Path
) -> None:
    """A path the target release adds to an unselected component stays excluded."""
    templates = template_source / "pytemplate"
    (templates / "templates" / "python" / "template" / "compose.yaml").write_text(
        "services: {}\n", "utf-8"
    )
    container = templates / "components" / "container.toml"
    container.write_text(
        container.read_text("utf-8").replace(
            'paths = ["Dockerfile", ".dockerignore"]',
            'paths = ["Dockerfile", ".dockerignore", "compose.yaml"]',
        ),
        "utf-8",
    )
    _release_new_template(template_source)

    update(UpdateRequest(project, to_ref="v99.0.0", apply=True))

    assert not (project / "compose.yaml").exists()
    assert NEW_README_LINE in (project / "README.md").read_text(encoding="utf-8")


def test_update_does_not_add_a_component_the_target_release_made_default(
    project: Path, template_source: Path
) -> None:
    profile = template_source / "pytemplate" / "templates" / "python" / "profile.toml"
    profile.write_text(
        profile.read_text("utf-8")
        .replace('default_components = ["cli"]', 'default_components = ["cli", "container"]')
        .replace('optional_components = ["container"]', "optional_components = []"),
        "utf-8",
    )
    _release_new_template(template_source)

    update(UpdateRequest(project, to_ref="v99.0.0", apply=True))

    manifest = tomllib.loads((project / ".pytemplate.toml").read_text(encoding="utf-8"))
    answers = yaml.safe_load((project / ".copier-answers.yml").read_text(encoding="utf-8"))
    assert not (project / "Dockerfile").exists()
    assert [entry["id"] for entry in manifest["components"]] == ["cli"]
    assert answers["components"] == ["cli"]


def test_update_keeps_unrelated_empty_directories(project: Path, template_source: Path) -> None:
    (project / "data" / "raw").mkdir(parents=True)
    _release_new_template(template_source)

    update(UpdateRequest(project, to_ref="v99.0.0", apply=True))

    assert (project / "data" / "raw").is_dir()


def test_unknown_target_release_is_an_update_error(project: Path) -> None:
    with pytest.raises(UpdateError, match="Cannot prepare the update to v404"):
        update(UpdateRequest(project, to_ref="v404", apply=True))
    assert _git(project, "status", "--porcelain") == ""
