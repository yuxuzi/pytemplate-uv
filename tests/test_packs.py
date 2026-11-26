"""Tests for explicitly selected external template packs."""

import hashlib
import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml
from cli_runner import make_runner

from pytemplate import api, packs
from pytemplate.configuration import load_render_request
from pytemplate.errors import PackError, RenderError
from pytemplate.main import app
from pytemplate.packs import is_git_source, open_catalog, pack_digest
from pytemplate.rendering import RenderRequest, plan, render

runner = make_runner()


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
    identity = ["-c", "user.name=Test", "-c", "user.email=test@example.com"]
    return subprocess.run(
        ["git", *identity, "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
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


# A shared test vector: pytemplate-hub's tests/test_fetch.py checks its digest against the same
# files and the same value, so a digest the hub records is one this package accepts. The digest
# format is stable (docs: Compatibility and versioning); never change this value in a 3.x release.
DIGEST_VECTOR_FILES = {
    "B.txt": b"upper\n",
    "a.txt": b"lower\n",
    "dir/x": b"\x00\xff",
    "dir/sub/y.txt": b"",
    "dir-y/z": b"z\n",
}
DIGEST_VECTOR = "fd6a0842ebb196f5b593281ec33403e9747a65fef2f70bb15246d556e8775bec"


def test_digest_matches_the_vector_shared_with_pytemplate_hub(tmp_path: Path) -> None:
    for name, data in DIGEST_VECTOR_FILES.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(data)

    assert pack_digest(tmp_path) == DIGEST_VECTOR
    assert api.pack_digest(tmp_path) == DIGEST_VECTOR


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
            "-y",
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


@pytest.mark.parametrize(
    "command",
    [
        ["list-profiles"],
        ["describe-profile", "tool"],
        ["list-components"],
        ["describe-component", "extra"],
    ],
)
def test_discovery_commands_check_the_pin(pack: Path, command: list[str]) -> None:
    commit = _tagged_pack(pack)
    source = ["--template", pack.as_uri(), "--template-ref", "v1.0.0", "--json"]

    moved = runner.invoke(app, [*command, *source, "--template-commit", "f" * 40])
    pinned = runner.invoke(app, [*command, *source, "--template-commit", commit])

    assert moved.exit_code == 1
    assert "tag may have moved" in moved.output
    assert pinned.exit_code == 0, pinned.output


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


def test_git_runs_without_prompts_and_with_a_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict[str, object]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs)
        raise subprocess.TimeoutExpired(command, 5)

    monkeypatch.setattr(packs.subprocess, "run", fake_run)
    monkeypatch.setenv("PYTEMPLATE_GIT_TIMEOUT", "5")

    with pytest.raises(PackError, match=r"https://example.invalid/pack.git.*within 5 s"):
        packs._clone("https://example.invalid/pack.git", None, tmp_path / "pack")

    env = seen[0]["env"]
    assert isinstance(env, dict)
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GCM_INTERACTIVE"] == "never"
    assert seen[0]["timeout"] == 5.0


@pytest.mark.parametrize("value", ["0", "-3", "soon"])
def test_a_bad_git_timeout_is_a_pack_error(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTEMPLATE_GIT_TIMEOUT", value)

    with pytest.raises(PackError, match="PYTEMPLATE_GIT_TIMEOUT"):
        packs._git_timeout()


def test_the_git_timeout_defaults_to_two_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEMPLATE_GIT_TIMEOUT", raising=False)

    assert packs._git_timeout() == 120.0


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_a_full_commit_hash_is_accepted_as_the_ref(pack: Path, tmp_path: Path) -> None:
    first = _tagged_pack(pack)
    (pack / "NOTES.md").write_text("later\n", encoding="utf-8")
    _commit_and_tag(pack, "v2.0.0")
    _git(pack, "config", "uploadpack.allowAnySHA1InWant", "true")

    with open_catalog(pack.as_uri(), first) as (_, source, root):
        assert source.commit == first
        assert source.ref == first
        assert not (root / "NOTES.md").exists()
        assert not (root / ".git").exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_an_unknown_commit_hash_is_a_pack_error(pack: Path, tmp_path: Path) -> None:
    _tagged_pack(pack)
    _git(pack, "config", "uploadpack.allowAnySHA1InWant", "true")

    with pytest.raises(PackError, match="Could not fetch template pack"):
        with open_catalog(pack.as_uri(), "0" * 40):
            pass


@pytest.mark.parametrize(
    "setting",
    [
        "{_tasks: [echo hi], _other: 1}",
        "{_migrations: []}",
        "{_jinja_extensions: [x.Ext]}",
        "{_external_data: {x: y.yml}}",
        "_external_data:\n  x: y.yml",
        '"_tasks": [echo hi]',
    ],
)
def test_flow_style_and_other_spellings_of_unsafe_settings_are_rejected(
    pack: Path, tmp_path: Path, setting: str
) -> None:
    (pack / "extra.yaml").write_text(setting + "\n", encoding="utf-8")

    with pytest.raises(PackError, match="declares '_"):
        render(_request(pack, tmp_path))


def test_an_unsafe_setting_in_an_included_file_is_rejected(pack: Path, tmp_path: Path) -> None:
    nested = pack / "parts"
    nested.mkdir()
    (nested / "more.yml").write_text("--- !include deeper.yml\n", encoding="utf-8")
    (nested / "deeper.yml").write_text("_tasks: [echo hi]\n", encoding="utf-8")
    copier_yml = pack / "copier.yml"
    copier_yml.write_text(
        copier_yml.read_text(encoding="utf-8") + "\n--- !include parts/more.yml\n", "utf-8"
    )

    with pytest.raises(PackError, match=r"deeper.yml declares '_tasks'"):
        render(_request(pack, tmp_path))


def test_an_include_outside_the_pack_is_rejected(pack: Path, tmp_path: Path) -> None:
    (tmp_path / "outside.yml").write_text("a: 1\n", encoding="utf-8")
    copier_yml = pack / "copier.yml"
    copier_yml.write_text(
        copier_yml.read_text(encoding="utf-8") + "\n--- !include ../outside.yml\n", "utf-8"
    )

    with pytest.raises(PackError, match="outside the pack"):
        render(_request(pack, tmp_path))


def test_unknown_yaml_tags_and_broken_yaml_are_rejected(pack: Path, tmp_path: Path) -> None:
    (pack / "extra.yml").write_text("a: !!python/object/apply:os.getcwd []\n", encoding="utf-8")
    with pytest.raises(PackError, match="YAML tag"):
        render(_request(pack, tmp_path))

    (pack / "extra.yml").write_text("a: [unclosed\n", encoding="utf-8")
    with pytest.raises(PackError, match="not valid YAML"):
        render(_request(pack, tmp_path))


@pytest.fixture(autouse=True)
def _isolated_cache(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Keep every test away from the real user cache."""
    cache = tmp_path_factory.mktemp("cache")
    monkeypatch.setenv("PYTEMPLATE_CACHE_DIR", str(cache))
    monkeypatch.delenv("PYTEMPLATE_NO_CACHE", raising=False)
    return cache


def _full_pin(pack: Path, tmp_path: Path) -> dict[str, str]:
    commit = _tagged_pack(pack)
    digest = plan(_pinned(pack, tmp_path)).source.digest
    assert digest is not None
    return {"template_commit": commit, "template_digest": digest}


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_a_pack_pinned_to_commit_and_digest_is_cached(
    pack: Path, tmp_path: Path, _isolated_cache: Path
) -> None:
    pins = _full_pin(pack, tmp_path)
    assert not (_isolated_cache / "packs").exists()

    render(_pinned(pack, tmp_path, **pins))

    entry = _isolated_cache / "packs" / f"{pins['template_commit']}-{pins['template_digest']}"
    assert (entry / "pytemplate-pack.toml").is_file()
    assert not (entry / ".git").exists()
    assert [item.name for item in (_isolated_cache / "packs").iterdir()] == [entry.name]

    # The repository can disappear: the second run comes from the cache.
    packs._remove_tree(pack / ".git")
    result = render(_pinned(pack, tmp_path, overwrite=True, **pins))
    assert result.source.commit == pins["template_commit"]
    assert result.source.digest == pins["template_digest"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_a_changed_cache_entry_is_discarded_and_fetched_again(
    pack: Path, tmp_path: Path, _isolated_cache: Path
) -> None:
    pins = _full_pin(pack, tmp_path)
    render(_pinned(pack, tmp_path, **pins))
    entry = _isolated_cache / "packs" / f"{pins['template_commit']}-{pins['template_digest']}"
    (entry / "tool" / "template" / "README.md.jinja").write_text("tampered\n", encoding="utf-8")

    result = render(_pinned(pack, tmp_path, overwrite=True, **pins))

    assert pack_digest(entry) == pins["template_digest"]
    assert result.source.digest == pins["template_digest"]
    assert "tampered" not in (result.project_path / "README.md").read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_pack_cache_is_skipped_when_not_fully_pinned_or_disabled(
    pack: Path, tmp_path: Path, _isolated_cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pins = _full_pin(pack, tmp_path)

    render(_pinned(pack, tmp_path, template_commit=pins["template_commit"]))
    render(_pinned(pack, tmp_path, overwrite=True, template_digest=pins["template_digest"]))
    render(_pinned(pack, tmp_path, overwrite=True, use_cache=False, **pins))
    monkeypatch.setenv("PYTEMPLATE_NO_CACHE", "1")
    render(_pinned(pack, tmp_path, overwrite=True, **pins))

    assert not (_isolated_cache / "packs").exists()


@pytest.mark.parametrize(
    ("platform", "env", "expected"),
    [
        ("darwin", {}, ("Library", "Caches", "pytemplate-uv")),
        ("linux", {}, (".cache", "pytemplate-uv")),
        ("linux", {"XDG_CACHE_HOME": "XDG"}, ("XDG", "pytemplate-uv")),
        ("win32", {"LOCALAPPDATA": "LOCAL"}, ("LOCAL", "pytemplate-uv", "Cache")),
    ],
)
def test_cache_dir_follows_the_platform(
    platform: str,
    env: dict[str, str],
    expected: tuple[str, ...],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEMPLATE_CACHE_DIR")
    for name in ("XDG_CACHE_HOME", "LOCALAPPDATA"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, str(tmp_path / value))
    monkeypatch.setattr(packs.sys, "platform", platform)
    monkeypatch.setattr(packs.Path, "home", lambda: tmp_path / "home")
    base = tmp_path if env else tmp_path / "home"

    assert packs.cache_dir() == base.joinpath(*expected)


def test_cache_dir_can_be_overridden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTEMPLATE_CACHE_DIR", str(tmp_path / "mine"))

    assert packs.cache_dir() == tmp_path / "mine"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_crlf_settings_do_not_change_a_pack_checked_out_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.txt").write_bytes(b"one\ntwo\n")
    (repo / ".gitattributes").write_text("* text=auto\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "pack")
    # Simulate a Windows user's global git config: CRLF checkouts, native line endings.
    global_config = tmp_path / "gitconfig"
    global_config.write_text("[core]\n\teol = crlf\n\tautocrlf = true\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    dest = tmp_path / "dest"

    packs._clone(str(repo), None, dest)

    assert b"\r\n" not in (dest / "a.txt").read_bytes()
    assert (dest / "a.txt").read_bytes() == b"one\ntwo\n"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_a_pack_with_a_git_submodule_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "pack")
    existing = _git(repo, "rev-parse", "HEAD")
    # A gitlink (mode 160000) records a commit in another repository, which git never fetches.
    _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{existing},sub")
    _git(repo, "commit", "-q", "-m", "add a submodule")

    with pytest.raises(PackError, match="submodule"):
        packs._clone(str(repo), None, tmp_path / "dest")
