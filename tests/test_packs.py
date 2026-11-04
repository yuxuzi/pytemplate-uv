"""Tests for explicitly selected external template packs."""

import hashlib
import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from pytemplate.configuration import load_render_request
from pytemplate.errors import PackError, RenderError
from pytemplate.main import app
from pytemplate.packs import is_git_source, open_catalog, pack_digest
from pytemplate.rendering import RenderRequest, plan, render
from pytemplate.updating import _manifest_source

runner = CliRunner()


def _request(pack: Path | str, output: Path, **kwargs: object) -> RenderRequest:
    return RenderRequest(
        profile_id="tool",
        project_name="demo-tool",
        output_dir=output,
        no_input=True,
        template=str(pack),
        **kwargs,  # type: ignore[arg-type]
    )


def test_pack_catalog_is_loaded_from_the_pack_only(pack: Path) -> None:
    with open_catalog(str(pack)) as (catalog, source, _):
        assert [profile.identifier for profile in catalog.profiles] == ["tool"]
        assert [component.identifier for component in catalog.components] == ["extra"]
        assert (source.kind, source.pack_id, source.pack_version) == ("pack", "demo-pack", "1.0.0")


def test_pack_renders_and_is_recorded(pack: Path, tmp_path: Path) -> None:
    (tmp_path / "out").mkdir()

    result = render(_request(pack, tmp_path / "out", components=("extra",)))

    project = result.project_path
    manifest = tomllib.loads((project / ".pytemplate.toml").read_text(encoding="utf-8"))
    answers = yaml.safe_load((project / ".copier-answers.yml").read_text(encoding="utf-8"))
    assert (project / "demo_tool" / "extra.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert manifest["template"] == {
        "kind": "pack",
        "source": str(pack),
        "pack": "demo-pack",
        "pack_version": "1.0.0",
    }
    assert {entry["path"]: entry["owner"] for entry in manifest["files"]}[
        "demo_tool/extra.py"
    ] == "extra"
    assert answers["_src_path"] == str(pack)
    assert "_commit" not in answers


def test_pack_components_are_optional(pack: Path, tmp_path: Path) -> None:
    project = render(_request(pack, tmp_path)).project_path

    assert not (project / "demo_tool" / "extra.py").exists()


def test_bundled_profiles_are_not_visible_through_a_pack(pack: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown profile 'python'. Available profiles: tool"):
        render(RenderRequest("python", "demo", tmp_path, template=str(pack)))


@pytest.mark.parametrize(
    "setting", ["_tasks: [echo hi]", "_migrations: []", "_jinja_extensions: [x.Ext]"]
)
def test_packs_declaring_code_execution_are_rejected(
    pack: Path, tmp_path: Path, setting: str
) -> None:
    copier_yml = pack / "copier.yml"
    copier_yml.write_text(setting + "\n" + copier_yml.read_text(encoding="utf-8"), "utf-8")

    with pytest.raises(PackError, match=f"declares '{setting.split(':')[0]}'"):
        render(_request(pack, tmp_path))
    assert list(tmp_path.iterdir()) == [pack]


def test_packs_containing_symlinks_are_rejected(pack: Path, tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("token", encoding="utf-8")
    try:
        (pack / "tool" / "template" / "leak.txt").symlink_to(secret)
    except OSError:
        pytest.skip("symlinks are not available on this platform")

    with pytest.raises(PackError, match="symlink"):
        render(_request(pack, tmp_path / "out"))


def test_directory_without_a_pack_manifest_is_rejected(pack: Path, tmp_path: Path) -> None:
    (pack / "pytemplate-pack.toml").unlink()

    with pytest.raises(PackError, match="pytemplate-pack.toml is missing"):
        render(_request(pack, tmp_path))


def test_pack_with_an_unsupported_contract_is_rejected(pack: Path, tmp_path: Path) -> None:
    manifest = pack / "pytemplate-pack.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("contract = 1", "contract = 2"), "utf-8"
    )

    with pytest.raises(PackError, match="'contract' must be 1"):
        render(_request(pack, tmp_path))


def test_pack_manifest_errors_name_the_pack(pack: Path, tmp_path: Path) -> None:
    profile = pack / "tool" / "profile.toml"
    profile.write_text(profile.read_text(encoding="utf-8") + 'colour = "red"\n', "utf-8")

    with pytest.raises(PackError, match=r"'demo-pack': tool/profile.toml: unknown key\(s\) colour"):
        render(_request(pack, tmp_path))


def test_missing_pack_directory_is_reported(tmp_path: Path) -> None:
    with pytest.raises(PackError, match="does not exist"):
        render(_request(tmp_path / "missing", tmp_path))


def test_profile_without_an_answers_template_fails_clearly(pack: Path, tmp_path: Path) -> None:
    (pack / "tool" / "template" / "{{ _copier_conf.answers_file }}.jinja").unlink()

    with pytest.raises(RenderError, match="did not write .copier-answers.yml"):
        render(_request(pack, tmp_path))


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_pack_is_cloned_from_a_git_tag(
    pack: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for prefix in ("GIT_AUTHOR", "GIT_COMMITTER"):
        monkeypatch.setenv(f"{prefix}_NAME", "Test")
        monkeypatch.setenv(f"{prefix}_EMAIL", "test@example.com")

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
            cwd=pack,
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "pack")
    git("tag", "v1.0.0")
    (tmp_path / "out").mkdir()

    result = render(_request(pack, tmp_path / "out", template_ref="v1.0.0"))

    manifest = tomllib.loads((result.project_path / ".pytemplate.toml").read_text("utf-8"))
    answers = yaml.safe_load((result.project_path / ".copier-answers.yml").read_text("utf-8"))
    assert manifest["template"]["ref"] == "v1.0.0"
    assert answers["_commit"] == "v1.0.0"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_unknown_git_ref_is_a_pack_error(pack: Path, tmp_path: Path) -> None:
    with pytest.raises(PackError, match="Could not clone"):
        render(_request(pack, tmp_path, template_ref="v404"))


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("gh:org/repo", True),
        ("https://example.com/pack.git", True),
        ("git@github.com:org/repo.git", True),
        ("./packs/demo", False),
        ("C:/packs/demo", False),
    ],
)
def test_git_sources_are_recognised(source: str, expected: bool) -> None:
    assert is_git_source(source) is expected


def test_plan_lists_pack_files_without_writing(pack: Path, tmp_path: Path) -> None:
    planned = plan(_request(pack, tmp_path, components=("extra",)))

    assert planned.files == (
        ".copier-answers.yml",
        ".pytemplate.toml",
        "README.md",
        "demo_tool/__init__.py",
        "demo_tool/extra.py",
    )
    assert planned.resolution.dependencies == ("pydantic>=2", "rich>=13.7")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["pack"]


def test_request_file_resolves_a_relative_pack_path(pack: Path, tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text('project_name = "demo-tool"\nprofile = "tool"\ntemplate = "pack"\n', "utf-8")

    request = load_render_request(config)

    assert request.template == str(pack)


def test_cli_lists_and_describes_pack_contents(pack: Path) -> None:
    profiles = runner.invoke(app, ["list-profiles", "--template", str(pack), "--json"])
    component = runner.invoke(
        app, ["describe-component", "extra", "--template", str(pack), "--json"]
    )

    assert profiles.exit_code == 0, profiles.output
    assert [item["identifier"] for item in json.loads(profiles.output)] == ["tool"]
    assert json.loads(component.output)["paths"] == ["{package}/extra.py"]


def test_cli_reports_a_bad_pack_as_an_invalid_request(tmp_path: Path) -> None:
    result = runner.invoke(app, ["list-profiles", "--template", str(tmp_path), "--json"])

    assert result.exit_code == 1
    assert json.loads(result.output)["error"]["type"] == "PackError"


def _tagged_pack(pack: Path) -> str:
    """Make ``pack`` a git repository tagged v1.0.0 and return the tagged commit."""
    _git(pack, "init", "-q")
    return _commit_and_tag(pack, "v1.0.0")


def _git(directory: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit_and_tag(pack: Path, tag: str) -> str:
    _git(pack, "add", "-A")
    _git(pack, "commit", "-q", "--allow-empty", "-m", tag)
    _git(pack, "tag", "--force", tag)
    return _git(pack, "rev-parse", "HEAD")


def _pinned(pack: Path, tmp_path: Path, **pins: str | None) -> RenderRequest:
    (tmp_path / "out").mkdir(exist_ok=True)
    return RenderRequest(
        profile_id="tool",
        project_name="demo",
        output_dir=tmp_path / "out",
        no_input=True,
        template=pack.as_uri(),
        template_ref="v1.0.0",
        **pins,
    )


def test_digest_is_stable_and_ordered_by_path_components(tmp_path: Path) -> None:
    for name, text in (("agent-b.txt", "b"), ("agent/a.txt", "a"), ("LICENSE", "l")):
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(text.encode())
    framed = b"LICENSE\0l\0" + b"agent/a.txt\0a\0" + b"agent-b.txt\0b\0"

    assert pack_digest(tmp_path) == hashlib.sha256(framed).hexdigest()
    assert pack_digest(tmp_path) == (
        "8404d1cecfa0e474b04aef81a1be1d97ec8eaa8ddde47a5238ab5057bec4ccdb"
    )


def test_git_pack_records_its_commit_and_digest(pack: Path, tmp_path: Path) -> None:
    commit = _tagged_pack(pack)

    result = render(_pinned(pack, tmp_path))

    template = tomllib.loads((result.project_path / ".pytemplate.toml").read_text("utf-8"))[
        "template"
    ]
    assert template["commit"] == commit
    assert len(template["digest"]) == 64
    answers = yaml.safe_load((result.project_path / ".copier-answers.yml").read_text("utf-8"))
    assert answers["_commit"] == "v1.0.0"


def test_directory_pack_records_no_commit_or_digest(pack: Path, tmp_path: Path) -> None:
    (tmp_path / "out").mkdir()
    request = RenderRequest(
        profile_id="tool",
        project_name="demo",
        output_dir=tmp_path / "out",
        no_input=True,
        template=str(pack),
    )

    template = tomllib.loads(
        (render(request).project_path / ".pytemplate.toml").read_text("utf-8")
    )["template"]

    assert "commit" not in template
    assert "digest" not in template


def test_matching_pin_renders(pack: Path, tmp_path: Path) -> None:
    commit = _tagged_pack(pack)
    digest = plan(_pinned(pack, tmp_path)).source.digest

    result = render(_pinned(pack, tmp_path, template_commit=commit, template_digest=digest))

    assert result.source.commit == commit
    assert result.source.digest == digest


def test_annotated_tag_pins_to_its_commit(pack: Path, tmp_path: Path) -> None:
    _git(pack, "init", "-q")
    _git(pack, "add", "-A")
    _git(pack, "commit", "-q", "-m", "pack")
    _git(pack, "tag", "-a", "v1.0.0", "-m", "release")
    commit = _git(pack, "rev-parse", "HEAD")

    assert plan(_pinned(pack, tmp_path, template_commit=commit)).source.commit == commit


def test_moved_tag_is_refused_and_writes_nothing(pack: Path, tmp_path: Path) -> None:
    commit = _tagged_pack(pack)
    (pack / "tool" / "template" / "README.md.jinja").write_text("changed\n", encoding="utf-8")
    _commit_and_tag(pack, "v1.0.0")

    with pytest.raises(PackError, match="tag may have moved"):
        render(_pinned(pack, tmp_path, template_commit=commit))

    assert not (tmp_path / "out" / "demo").exists()


def test_changed_digest_is_refused_and_writes_nothing(pack: Path, tmp_path: Path) -> None:
    _tagged_pack(pack)

    with pytest.raises(PackError, match="has digest"):
        render(_pinned(pack, tmp_path, template_digest="0" * 64))

    assert not (tmp_path / "out" / "demo").exists()


def test_pin_is_checked_by_plan_too(pack: Path, tmp_path: Path) -> None:
    _tagged_pack(pack)

    with pytest.raises(PackError, match="tag may have moved"):
        plan(_pinned(pack, tmp_path, template_commit="f" * 40))


@pytest.mark.parametrize(
    ("template", "ref"),
    [(None, None), ("./pack", None), ("gh:org/pack", None)],
)
def test_pin_needs_a_git_source_and_a_ref(template: str | None, ref: str | None) -> None:
    with (
        pytest.raises(PackError, match="also pass a git --template"),
        open_catalog(template, ref, commit="f" * 40),
    ):
        pass


@pytest.mark.parametrize(
    ("pin", "value", "message"),
    [
        ("commit", "abc123", "full lowercase commit"),
        ("commit", "F" * 40, "full lowercase commit"),
        ("commit", "--upload-pack=evil", "full lowercase commit"),
        ("digest", "abc123", "lowercase SHA-256"),
    ],
)
def test_malformed_pin_is_refused_before_fetching(pin: str, value: str, message: str) -> None:
    with (
        pytest.raises(PackError, match=message),
        open_catalog("gh:org/does-not-exist", "v1", **{pin: value}),
    ):
        pass


def test_cli_refuses_a_moved_tag_as_an_invalid_request(pack: Path, tmp_path: Path) -> None:
    _tagged_pack(pack)
    (tmp_path / "out").mkdir()

    result = runner.invoke(
        app,
        [
            "create",
            "demo",
            "-p",
            "tool",
            "--no-input",
            "-o",
            str(tmp_path / "out"),
            "--template",
            pack.as_uri(),
            "--template-ref",
            "v1.0.0",
            "--template-commit",
            "f" * 40,
        ],
    )

    assert result.exit_code == 1
    assert not (tmp_path / "out" / "demo").exists()


def test_request_file_carries_the_pin(pack: Path, tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text(
        'project_name = "demo"\n'
        'profile = "tool"\n'
        'template = "gh:org/pack"\n'
        'template_ref = "v1"\n'
        f'template_commit = "{"a" * 40}"\n'
        f'template_digest = "{"b" * 64}"\n',
        encoding="utf-8",
    )

    request = load_render_request(config)

    assert request.template_commit == "a" * 40
    assert request.template_digest == "b" * 64


def test_update_does_not_keep_the_previous_tags_commit_or_digest() -> None:
    manifest = {
        "template": {
            "kind": "pack",
            "source": "gh:org/pack",
            "ref": "v1.0.0",
            "commit": "a" * 40,
            "digest": "b" * 64,
        }
    }

    source = _manifest_source(manifest, {})

    assert source.ref == "v1.0.0"
    assert source.commit is None
    assert source.digest is None
