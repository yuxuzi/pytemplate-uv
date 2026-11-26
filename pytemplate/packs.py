"""Explicitly selected external template packs and the template source of a project."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from pytemplate.errors import PackError
from pytemplate.profiles import (
    CONTRACT_VERSION,
    Catalog,
    ManifestError,
    bundled_catalog,
    load_catalog,
)
from pytemplate.suggestions import did_you_mean

PACK_FILE = "pytemplate-pack.toml"
BUNDLED = "bundled"
# Copier settings that run code, load extensions, or fetch data; packs must never declare them.
_UNSAFE_SETTINGS = ("_tasks", "_migrations", "_jinja_extensions", "_external_data")
_GIT_PREFIXES = ("gh:", "gl:", "git+", "https://", "http://", "ssh://", "git@", "file://")
_PACK_KEYS = frozenset(
    {"contract", "id", "name", "description", "version", "categories", "keywords"}
)
MAX_KEYWORDS = 12
MAX_KEYWORD_LENGTH = 30
# The fixed category vocabulary that pytemplate-hub files packs under. A new category is added in
# a pytemplate-uv release, so every pack, check, and listing agrees on the same list.
PACK_CATEGORIES: tuple[str, ...] = ("cli", "library", "web", "worker", "data", "ai", "quant")
_COMMIT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PackManifest:
    """The contents of a pack's ``pytemplate-pack.toml``.

    ``categories`` and ``keywords`` are optional. Each category must be one of
    ``PACK_CATEGORIES``; keywords are free search words, checked for shape only.
    """

    id: str
    name: str
    description: str
    version: str
    categories: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class TemplateSource:
    """Where a project's templates came from, as recorded in its manifest."""

    kind: str
    location: str
    ref: str | None = None
    pack_id: str | None = None
    pack_version: str | None = None
    commit: str | None = None
    digest: str | None = None
    hub: str | None = None

    @property
    def is_bundled(self) -> bool:
        """Return whether the templates ship inside this package."""
        return self.kind == BUNDLED


def is_git_source(location: str) -> bool:
    """Return whether ``location`` names a git repository rather than a local directory."""
    return location.startswith(_GIT_PREFIXES) or location.endswith(".git")


def _clone_url(location: str) -> str:
    for prefix, host in (("gh:", "https://github.com/"), ("gl:", "https://gitlab.com/")):
        if location.startswith(prefix):
            return f"{host}{location.removeprefix(prefix)}.git"
    return location.removeprefix("git+")


DEFAULT_GIT_TIMEOUT = 120.0
_GIT_TIMEOUT_ENV = "PYTEMPLATE_GIT_TIMEOUT"


def _git_timeout() -> float:
    """Return the seconds a git command may run, from ``PYTEMPLATE_GIT_TIMEOUT`` or 120."""
    raw = os.environ.get(_GIT_TIMEOUT_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_GIT_TIMEOUT
    try:
        seconds = float(raw)
    except ValueError:
        seconds = 0.0
    if seconds <= 0:
        raise PackError(f"{_GIT_TIMEOUT_ENV} must be a positive number of seconds, got '{raw}'.")
    return seconds


def _git_environment() -> dict[str, str]:
    """Return an environment in which git never waits for a person to type a credential."""
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}


def _run_git(
    git: str, args: Sequence[str], *, location: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run git without prompts and with a timeout; a timeout is a ``PackError``."""
    timeout = _git_timeout()
    try:
        return subprocess.run(
            [git, "-c", "core.autocrlf=false", "-c", "core.eol=lf", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            env=_git_environment(),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise PackError(
            f"Template pack '{location}': git {args[0]} did not finish within {timeout:g} s and "
            f"was stopped. Check the URL and your network, or raise {_GIT_TIMEOUT_ENV}."
        ) from error


def _fetch_commit(git: str, url: str, commit: str, destination: Path, location: str) -> None:
    """Fetch exactly ``commit`` (a full hash) into ``destination`` and check it out."""
    destination.mkdir(parents=True)
    for args in (
        ["init", "--quiet"],
        ["fetch", "--quiet", "--depth", "1", url, commit],
        ["checkout", "--quiet", "FETCH_HEAD"],
    ):
        completed = _run_git(git, args, location=location, cwd=destination)
        if completed.returncode != 0:
            raise PackError(
                f"Could not fetch template pack '{location}' at commit {commit}: "
                f"{completed.stderr.strip()}"
            )


def _clone(location: str, ref: str | None, destination: Path) -> str:
    """Clone ``location`` at ``ref`` into a plain checkout and return its commit.

    ``ref`` is a branch, a tag, or a full commit hash. Line endings are not converted, even when
    the pack's ``.gitattributes`` sets ``text=auto`` and the machine's git config asks for CRLF
    (as Windows does), so a pack has the same bytes and digest on every machine.
    """
    git = shutil.which("git")
    if git is None:
        raise PackError(f"git is required to use the template pack '{location}'; install git.")
    url = _clone_url(location)
    if Path(url).is_dir():
        url = Path(url).resolve().as_uri()
    if ref and _COMMIT.match(ref):
        _fetch_commit(git, url, ref, destination, location)
    else:
        command = ["clone", "--quiet", "--depth", "1"]
        if ref:
            command += ["--branch", ref]
        completed = _run_git(git, [*command, url, str(destination)], location=location)
        if completed.returncode != 0:
            raise PackError(
                f"Could not clone template pack '{location}'"
                f"{f' at {ref}' if ref else ''}: {completed.stderr.strip()}"
            )
    commit = _run_git(git, ["rev-parse", "HEAD"], location=location, cwd=destination)
    if commit.returncode != 0:
        raise PackError(f"Could not read the commit of '{location}': {commit.stderr.strip()}")
    # A submodule (a gitlink, mode 160000) is never fetched, so the digest would silently omit it.
    listing = _run_git(git, ["ls-tree", "-r", "-z", "HEAD"], location=location, cwd=destination)
    if listing.returncode != 0:
        raise PackError(f"Could not list the files of '{location}': {listing.stderr.strip()}")
    for entry in listing.stdout.split("\0"):
        mode, _, name = entry.partition("\t")
        if mode.split(" ", 1)[0] == "160000":
            raise PackError(
                f"Template pack '{location}' contains a git submodule, which is not allowed: {name}"
            )
    # Render from a plain checkout; the source, ref, and commit are recorded separately.
    _remove_tree(destination / ".git")
    return commit.stdout.strip()


def _make_writable_and_retry(function: Any, path: str, _: object) -> None:
    """Remove read-only git objects on Windows."""
    os.chmod(path, stat.S_IWRITE)
    function(path)


def _remove_tree(path: Path) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=_make_writable_and_retry)


def pack_digest(root: Path) -> str:
    """Return a SHA-256 over every file's relative path and bytes under ``root``.

    Files are hashed in order of their path components, compared as case-sensitive strings, so the
    result is the same on every operating system. Each path (with forward slashes) and each file's
    bytes are followed by a NUL byte. ``root`` must not contain ``.git``. File modes (such as the
    executable bit) and empty directories are not part of the digest.
    """
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).parts):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0")
            digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def _check_pin(
    template: str | None, ref: str | None, commit: str | None, digest: str | None
) -> None:
    """Reject a pin that could not be verified, before anything is fetched."""
    if commit is None and digest is None:
        return
    if template is None or not is_git_source(template) or not ref:
        raise PackError(
            "A template commit or digest pins a git template pack: "
            "also pass a git --template and its --template-ref."
        )
    if commit is not None and not _COMMIT.match(commit):
        raise PackError(f"Template commit must be a full lowercase commit hash, got '{commit}'.")
    if digest is not None and not _DIGEST.match(digest):
        raise PackError(f"Template digest must be a lowercase SHA-256 hash, got '{digest}'.")


def _yaml_documents(path: Path) -> tuple[list[Any], list[str]]:
    """Parse every document of a pack YAML file and list the files it ``!include``s.

    Copier's ``!include`` tag is tolerated and not followed here; any other tag is refused.
    """
    import yaml

    includes: list[str] = []

    class Loader(yaml.SafeLoader):
        """A safe loader that records Copier's ``!include`` tag instead of resolving it."""

    def include(loader: yaml.SafeLoader, node: yaml.Node) -> None:
        if isinstance(node, yaml.ScalarNode):
            includes.append(str(node.value))
        elif isinstance(node, yaml.SequenceNode):
            includes.extend(str(loader.construct_object(item)) for item in node.value)

    def refuse(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> None:
        raise PackError(f"Template pack file {path.name} uses the YAML tag '{node.tag}'.")

    Loader.add_constructor("!include", include)
    Loader.add_multi_constructor("", refuse)
    try:
        documents = list(yaml.load_all(path.read_text(encoding="utf-8"), Loader=Loader))
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise PackError(f"Template pack file {path.name} is not valid YAML: {error}") from error
    return documents, includes


def _included_files(root: Path, config: Path, names: Sequence[str]) -> list[Path]:
    """Return the files ``config`` includes, which must stay inside the pack."""
    found: list[Path] = []
    for name in names:
        if "{{" in name or "{%" in name:
            raise PackError(
                f"Template pack file {config.name} includes '{name}', which cannot be checked; "
                "name the included file without a template expression."
            )
        for candidate in sorted(config.parent.glob(name)):
            resolved = candidate.resolve()
            if root.resolve() not in resolved.parents:
                raise PackError(
                    f"Template pack file {config.name} includes '{name}', outside the pack."
                )
            if resolved.is_file():
                found.append(resolved)
    return found


def _check_settings(root: Path) -> None:
    """Reject a pack whose Copier configuration declares a setting that runs code."""
    pending = [*root.glob("*.yml"), *root.glob("*.yaml")]
    seen: set[Path] = set()
    while pending:
        config = pending.pop().resolve()
        if config in seen or not config.is_file():
            continue
        seen.add(config)
        documents, includes = _yaml_documents(config)
        for document in documents:
            if isinstance(document, dict):
                for setting in _UNSAFE_SETTINGS:
                    if setting in document:
                        raise PackError(
                            f"Template pack file {config.name} declares '{setting}', which "
                            "pytemplate never runs; remove it from the pack."
                        )
        pending.extend(_included_files(root, config, includes))


def _check_safe(root: Path) -> None:
    """Reject symlinks (Copier would copy their targets) and code-running Copier settings."""
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PackError(
                f"Template pack contains a symlink, which is not allowed: {path.relative_to(root)}"
            )
    _check_settings(root)


def _categories(data: dict[str, Any]) -> tuple[str, ...]:
    value = data.get("categories", [])
    allowed = ", ".join(PACK_CATEGORIES)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PackError(
            f"{PACK_FILE}: 'categories' must be a list of category ids ({allowed}), got {value!r}."
        )
    for item in value:
        if item not in PACK_CATEGORIES:
            raise PackError(
                f"{PACK_FILE}: unknown category {item!r}; use one of: {allowed}."
                + did_you_mean(item, PACK_CATEGORIES)
            )
    if len(set(value)) != len(value):
        raise PackError(f"{PACK_FILE}: each category may be listed only once, got {value!r}.")
    return tuple(value)


def _keywords(data: dict[str, Any]) -> tuple[str, ...]:
    value = data.get("keywords", [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PackError(f"{PACK_FILE}: 'keywords' must be a list of strings, got {value!r}.")
    if len(value) > MAX_KEYWORDS:
        raise PackError(
            f"{PACK_FILE}: 'keywords' has {len(value)} entries; at most {MAX_KEYWORDS} are allowed."
        )
    for item in value:
        if not item or item != item.strip() or item != item.lower():
            raise PackError(
                f"{PACK_FILE}: keyword {item!r} must be lowercase, with no spaces at either end."
            )
        if len(item) > MAX_KEYWORD_LENGTH:
            raise PackError(
                f"{PACK_FILE}: keyword {item!r} is {len(item)} characters; at most "
                f"{MAX_KEYWORD_LENGTH} are allowed."
            )
    return tuple(value)


def read_pack_manifest(root: Path) -> PackManifest:
    """Read and check the ``pytemplate-pack.toml`` of the pack at ``root``.

    Raises ``PackError`` naming the file and key when the manifest is missing, malformed, or has
    a key of the wrong shape.
    """
    manifest = root / PACK_FILE
    if not manifest.is_file():
        raise PackError(f"{root} is not a template pack: {PACK_FILE} is missing.")
    try:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise PackError(f"{PACK_FILE} is not valid TOML: {error}") from error
    unknown = sorted(set(data) - _PACK_KEYS)
    if unknown:
        raise PackError(f"{PACK_FILE}: unknown key(s) {', '.join(unknown)}.")
    if data.get("contract") != CONTRACT_VERSION:
        raise PackError(
            f"{PACK_FILE}: 'contract' must be {CONTRACT_VERSION}, got {data.get('contract')!r}."
        )
    for key in ("id", "name", "description", "version"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise PackError(f"{PACK_FILE}: key '{key}' must be a non-empty string.")
    if not (root / "copier.yml").is_file():
        raise PackError(f"{root} is not a template pack: copier.yml is missing.")
    return PackManifest(
        id=str(data["id"]),
        name=str(data["name"]),
        description=str(data["description"]),
        version=str(data["version"]),
        categories=_categories(data),
        keywords=_keywords(data),
    )


def cache_dir() -> Path:
    """Return the directory for cached template packs.

    ``PYTEMPLATE_CACHE_DIR`` wins; otherwise the user cache directory of the platform.
    """
    override = os.environ.get("PYTEMPLATE_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "pytemplate-uv"
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        return (
            (Path(base) if base else Path.home() / "AppData" / "Local") / "pytemplate-uv" / "Cache"
        )
    base = os.environ.get("XDG_CACHE_HOME")
    return (Path(base) if base else Path.home() / ".cache") / "pytemplate-uv"


def _cache_enabled(use_cache: bool) -> bool:
    disabled = os.environ.get("PYTEMPLATE_NO_CACHE", "").strip().lower()
    return use_cache and disabled in ("", "0", "false", "no")


def _check_fetched(
    template: str, ref: str | None, fetched: str, contents: str, commit: str, digest: str
) -> None:
    if fetched != commit:
        raise PackError(
            f"Template pack '{template}' at {ref} is commit {fetched}, not the pinned "
            f"{commit}. The tag may have moved; nothing was rendered."
        )
    if contents != digest:
        raise PackError(
            f"Template pack '{template}' at {ref} has digest {contents}, not the pinned "
            f"{digest}. Nothing was rendered."
        )


def _cached_pack(template: str, ref: str | None, commit: str, digest: str) -> Path:
    """Return a verified local copy of a pack pinned to ``commit`` and ``digest``.

    The copy lives in the cache, keyed by both pins. It is verified against the digest on every
    use; a copy that no longer matches is discarded and fetched again. A new copy is written
    beside its final place and moved in with one rename, so a reader never sees half of one.
    """
    packs_dir = cache_dir() / "packs"
    target = packs_dir / f"{commit}-{digest}"
    if target.is_dir():
        if pack_digest(target) == digest:
            return target
        _remove_tree(target)
    packs_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".fetch-", dir=packs_dir))
    try:
        fetched = _clone(template, ref, staging / "pack")
        contents = pack_digest(staging / "pack")
        _check_fetched(template, ref, fetched, contents, commit, digest)
        try:
            os.replace(staging / "pack", target)
        except OSError:
            # Another process stored the same pack first.
            if not (target.is_dir() and pack_digest(target) == digest):
                raise
    finally:
        _remove_tree(staging)
    return target


@contextmanager
def open_catalog(
    template: str | None = None,
    ref: str | None = None,
    *,
    bundled_location: str = "",
    commit: str | None = None,
    digest: str | None = None,
    use_cache: bool = True,
) -> Iterator[tuple[Catalog, TemplateSource, Path]]:
    """Yield the catalog, its recorded source, and a local Copier template directory.

    ``template=None`` selects the bundled templates. Otherwise ``template`` is a local pack
    directory or a git source (``gh:org/repo``, a URL, or a local repository with ``ref``);
    git sources are cloned into a temporary directory that is removed afterwards.

    ``commit`` and ``digest`` pin a git source: a fetched pack is refused, before any of it is
    read, if ``ref`` no longer resolves to that commit or its files no longer match that digest.

    A git source pinned to both a commit and a digest is immutable, so it is cached under the
    user cache directory and verified against the digest on each use. A cache hit does not
    resolve ``ref`` again, so a tag moved after the first fetch is not noticed; the pinned files
    are still what renders. ``use_cache=False`` or the environment variable
    ``PYTEMPLATE_NO_CACHE=1`` fetches it every time instead.
    """
    _check_pin(template, ref, commit, digest)
    if template is None:
        catalog = bundled_catalog()
        with resources.as_file(catalog.root) as root:
            yield catalog, TemplateSource(kind=BUNDLED, location=bundled_location, ref=ref), root
        return

    with tempfile.TemporaryDirectory(prefix="pytemplate-pack-") as scratch:
        fetched: str | None = None
        if is_git_source(template) or ref:
            if (
                commit is not None
                and digest is not None
                and is_git_source(template)
                and _cache_enabled(use_cache)
            ):
                root = _cached_pack(template, ref, commit, digest)
                fetched = commit
            else:
                root = Path(scratch) / "pack"
                fetched = _clone(template, ref, root)
                if commit is not None and fetched != commit:
                    raise PackError(
                        f"Template pack '{template}' at {ref} is commit {fetched}, not the "
                        f"pinned {commit}. The tag may have moved; nothing was rendered."
                    )
            location = template
        else:
            root = Path(template).expanduser().resolve()
            if not root.is_dir():
                raise PackError(f"Template pack directory does not exist: {root}")
            location = str(root)
        _check_safe(root)
        contents = pack_digest(root) if fetched else None
        if digest is not None and contents != digest:
            raise PackError(
                f"Template pack '{template}' at {ref} has digest {contents}, not the pinned "
                f"{digest}. Nothing was rendered."
            )
        manifest = read_pack_manifest(root)
        pack_id, pack_version = manifest.id, manifest.version
        try:
            catalog = load_catalog(root, root / "components")
        except ManifestError as error:
            raise PackError(f"Template pack '{pack_id}': {error}") from error
        source = TemplateSource(
            kind="pack",
            location=location,
            ref=ref,
            pack_id=pack_id,
            pack_version=pack_version,
            commit=fetched,
            digest=contents,
        )
        yield catalog, source, root
