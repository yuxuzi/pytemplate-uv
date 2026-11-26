"""Tests for `--hub`: pins read from a pytemplate-hub entry, offline, over a file:// index."""

import json
import subprocess
from pathlib import Path

import pytest
from cli_runner import make_runner

from pytemplate import hub, packs
from pytemplate.main import app

runner = make_runner()
PACK = "yuxuzi/demo-pack"


def _git(directory: Path, *args: str) -> str:
    identity = ["-c", "user.name=Test", "-c", "user.email=test@example.com"]
    return subprocess.run(
        ["git", *identity, "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _tag(pack: Path, tag: str) -> str:
    """Commit the pack's files and point ``tag`` at the commit, replacing an older tag."""
    _git(pack, "add", "-A")
    _git(pack, "commit", "-q", "--allow-empty", "-m", tag)
    _git(pack, "tag", "--force", tag)
    return _git(pack, "rev-parse", "HEAD")


@pytest.fixture
def listed(pack: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Return the pins of a git pack tagged v1.0.0 and v2.0.0, and write a hub index for it."""
    _git(pack, "init", "-q")
    commit = _tag(pack, "v1.0.0")
    _git(pack, "tag", "--force", "v2.0.0")
    with packs.open_catalog(str(pack), "v1.0.0") as (_, source, _):
        digest = source.digest
    assert digest is not None
    # gh:yuxuzi/demo-pack clones the local fixture, so the tests stay offline.
    monkeypatch.setattr(packs, "_clone_url", lambda location: str(pack))
    monkeypatch.setenv("PYTEMPLATE_CACHE_DIR", str(tmp_path / "cache"))
    index = tmp_path / "hub" / "index"
    monkeypatch.setenv("PYTEMPLATE_HUB_URL", index.as_uri())
    write_entry(index, [_version("v1.0.0", commit, digest)])
    (tmp_path / "out").mkdir()
    return {"commit": commit, "digest": digest}


def _version(tag: str, commit: str, digest: str, **extra: str) -> str:
    lines = [
        "[[versions]]",
        f'tag = "{tag}"',
        f'commit = "{commit}"',
        f'digest = "{digest}"',
        'pack_version = "1.0.0"',
        'license = "MIT"',
        'checked_with = "pytemplate-uv==3.4.0"',
        'profiles = [{ id = "tool", lifecycle = "not-run" }]',
    ]
    lines += [f'{key} = "{value}"' for key, value in extra.items()]
    return "\n".join(lines) + "\n"


def write_entry(index: Path, versions: list[str], *, fmt: int = 1) -> None:
    """Write ``index/yuxuzi/demo-pack.toml`` with the given version tables."""
    text = f'format = {fmt}\nrepository = "https://github.com/{PACK}"\n' + "\n".join(versions)
    path = index / "yuxuzi" / "demo-pack.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _create(tmp_path: Path, *extra: str) -> object:
    return runner.invoke(
        app,
        ["create", "demo", "-p", "tool", "-y", "-o", str(tmp_path / "out"), *extra],
    )


def test_hub_creates_from_the_newest_listed_pins(listed: dict[str, str], tmp_path: Path) -> None:
    result = _create(tmp_path, "--hub", PACK)

    assert result.exit_code == 0, result.output
    assert "Using yuxuzi/demo-pack v1.0.0 (commit " in result.stderr
    assert "listed on the hub, not reviewed." in result.stderr
    manifest = (tmp_path / "out" / "demo" / ".pytemplate.toml").read_text(encoding="utf-8")
    assert 'source = "gh:yuxuzi/demo-pack"' in manifest
    assert 'hub = "yuxuzi/demo-pack"' in manifest
    assert f'commit = "{listed["commit"]}"' in manifest
    assert f'digest = "{listed["digest"]}"' in manifest


def test_hub_accepts_an_explicit_tag(listed: dict[str, str], tmp_path: Path) -> None:
    write_entry(
        _index_path(),
        [
            _version("v1.0.0", listed["commit"], listed["digest"]),
            _version("v2.0.0", listed["commit"], listed["digest"]),
        ],
    )

    result = _create(tmp_path, "-h", f"{PACK}@v2.0.0")

    assert result.exit_code == 0, result.output
    assert "Using yuxuzi/demo-pack v2.0.0" in result.stderr


def test_hub_json_carries_the_pins_and_keeps_stdout_clean(
    listed: dict[str, str], tmp_path: Path
) -> None:
    result = _create(tmp_path, "--hub", PACK, "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["template"]["hub"] == PACK
    assert payload["template"]["ref"] == "v1.0.0"
    assert payload["template"]["commit"] == listed["commit"]
    assert payload["template"]["digest"] == listed["digest"]
    assert "Using yuxuzi/demo-pack" in result.stderr


def test_yanked_tag_is_refused_and_names_the_newest(listed: dict[str, str], tmp_path: Path) -> None:
    write_entry(
        _index_path(),
        [
            _version("v1.0.0", listed["commit"], listed["digest"], yanked="broken"),
            _version("v2.0.0", listed["commit"], listed["digest"]),
        ],
    )

    result = _create(tmp_path, "--hub", f"{PACK}@v1.0.0")

    assert result.exit_code == 1
    assert "yanked" in result.output and "pass --hub yuxuzi/demo-pack@v2.0.0" in result.output
    assert not (tmp_path / "out" / "demo").exists()


def test_unknown_tag_lists_the_listed_tags(listed: dict[str, str], tmp_path: Path) -> None:
    result = _create(tmp_path, "--hub", f"{PACK}@v9.9.9")

    assert result.exit_code == 1
    assert (
        "Tag 'v9.9.9' is not listed for 'yuxuzi/demo-pack'. Listed tags: v1.0.0." in result.output
    )


def test_unknown_pack_is_not_listed(listed: dict[str, str], tmp_path: Path) -> None:
    result = _create(tmp_path, "--hub", "acme/foo")

    assert result.exit_code == 1
    assert "'acme/foo' is not listed on pytemplate-hub" in result.output
    assert "pass --template for a pack that is not listed" in result.output


def test_unsupported_entry_format_says_to_upgrade(listed: dict[str, str], tmp_path: Path) -> None:
    write_entry(_index_path(), [_version("v1.0.0", listed["commit"], listed["digest"])], fmt=2)

    result = _create(tmp_path, "--hub", PACK)

    assert result.exit_code == 1
    assert "format 2" in result.output and "Upgrade pytemplate-uv" in result.output


@pytest.mark.parametrize("spec", ["demo-pack", "yuxuzi/", "yuxuzi/demo pack"])
def test_malformed_hub_spec_shows_the_shape(
    listed: dict[str, str], tmp_path: Path, spec: str
) -> None:
    result = _create(tmp_path, "--hub", spec)

    assert result.exit_code == 1
    assert "--hub expects OWNER/PACK or OWNER/PACK@TAG" in result.output


@pytest.mark.parametrize(
    "flags",
    [
        ["--template", "gh:yuxuzi/demo-pack"],
        ["--template-ref", "v1.0.0"],
        ["--template-commit", "a" * 40],
        ["--template-digest", "b" * 64],
    ],
)
def test_hub_refuses_every_template_flag(
    listed: dict[str, str], tmp_path: Path, flags: list[str]
) -> None:
    result = _create(tmp_path, "--hub", PACK, *flags)

    assert result.exit_code == 1
    assert "--hub names the pack and its pins; drop --template" in result.output


def test_moved_tag_after_listing_is_refused_as_with_the_long_command(
    listed: dict[str, str], pack: Path, tmp_path: Path
) -> None:
    _tag(pack, "v1.0.0")  # the tag now points at a new commit

    result = _create(tmp_path, "--hub", PACK)

    assert result.exit_code == 1
    assert "The tag may have moved; nothing was rendered." in result.output
    assert not (tmp_path / "out" / "demo").exists()


def test_hub_is_a_lookup_only_the_pins_are_checked(listed: dict[str, str], tmp_path: Path) -> None:
    index = _index_path()
    write_entry(index, [_version("v1.0.0", listed["commit"], "c" * 64)])

    result = _create(tmp_path, "--hub", PACK)

    assert result.exit_code == 1
    assert "has digest" in result.output and "Nothing was rendered" in result.output


def test_reviewed_entries_say_who_reviewed_them(listed: dict[str, str], tmp_path: Path) -> None:
    index = _index_path()
    write_entry(index, [_version("v1.0.0", listed["commit"], listed["digest"], reviewed_by="octo")])

    result = _create(tmp_path, "--hub", PACK)

    assert result.exit_code == 0, result.output
    assert "reviewed by octo." in result.stderr


def test_list_commands_take_hub_too(listed: dict[str, str]) -> None:
    result = runner.invoke(app, ["list-profiles", "--hub", PACK, "--json"])

    assert result.exit_code == 0, result.output
    assert [item["identifier"] for item in json.loads(result.stdout)] == ["tool"]


def test_request_file_takes_hub(listed: dict[str, str], tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text(
        'project_name = "demo"\nprofile = "tool"\nno_input = true\n'
        f'output_dir = "{(tmp_path / "out").as_posix()}"\nhub = "{PACK}@v1.0.0"\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["create-from-config", str(config)])

    assert result.exit_code == 0, result.output
    assert "Using yuxuzi/demo-pack v1.0.0" in result.stderr


def test_request_file_refuses_hub_with_template(listed: dict[str, str], tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text(
        'project_name = "demo"\nprofile = "tool"\n'
        f'output_dir = "{(tmp_path / "out").as_posix()}"\nhub = "{PACK}"\n'
        'template = "gh:yuxuzi/demo-pack"\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["create-from-config", str(config)])

    assert result.exit_code == 1
    assert "--hub names the pack and its pins" in result.output


def test_hub_cannot_be_combined_with_a_request_file(listed: dict[str, str], tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text('project_name = "demo"\nprofile = "tool"\n', encoding="utf-8")

    result = runner.invoke(app, ["validate", str(config), "--hub", PACK])

    assert result.exit_code == 1
    assert "cannot be combined with a request file" in result.output


@pytest.mark.parametrize(
    "command",
    ["create", "create-project", "validate", "plan", "list-profiles", "list-components"],
)
def test_bare_dash_h_shows_help_on_each_hub_command(command: str) -> None:
    result = runner.invoke(
        app, [command, "-h"] if command.startswith("list") else [command, "demo", "-h"]
    )

    assert result.exit_code == 0, result.output
    assert "Usage" in result.output and "--hub" in result.output


def test_dash_h_before_another_option_is_help_and_help_is_unchanged() -> None:
    assert runner.invoke(app, ["create", "--help"]).exit_code == 0
    result = runner.invoke(app, ["create", "demo", "-h", "-y"])

    assert result.exit_code == 0
    assert "Usage" in result.output


def test_root_dash_h_is_still_unused() -> None:
    result = runner.invoke(app, ["-h"])

    assert result.exit_code != 0
    assert "No such option" in result.output


def _index_path() -> Path:
    """Return the index directory the ``listed`` fixture points PYTEMPLATE_HUB_URL at."""
    import os
    from urllib.parse import urlparse
    from urllib.request import url2pathname

    return Path(url2pathname(urlparse(os.environ["PYTEMPLATE_HUB_URL"]).path))


class _FakeResponse:
    """Stand-in for an HTTP response that serves at most the bytes asked for."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._payload if size < 0 else self._payload[:size]


def test_a_hub_entry_over_one_mib_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    limit = 1024 * 1024
    monkeypatch.setattr(
        hub.urllib.request, "urlopen", lambda *_, **__: _FakeResponse(b"x" * (limit + 1))
    )

    with pytest.raises(hub.HubError, match="larger than 1 MiB.*--template pins"):
        hub._read_entry("https://hub.invalid/yuxuzi/demo-pack.toml", PACK)


def test_a_hub_entry_of_exactly_one_mib_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    limit = 1024 * 1024
    monkeypatch.setattr(hub.urllib.request, "urlopen", lambda *_, **__: _FakeResponse(b"x" * limit))

    assert hub._read_entry("https://hub.invalid/yuxuzi/demo-pack.toml", PACK) == b"x" * limit
