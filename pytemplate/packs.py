"""Explicitly selected external template packs and the template source of a project."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Iterator
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

PACK_FILE = "pytemplate-pack.toml"
BUNDLED = "bundled"
# Copier settings that run code or load extensions; packs must never declare them.
_UNSAFE_SETTINGS = re.compile(r"^(_tasks|_migrations|_jinja_extensions)\s*:", re.MULTILINE)
_GIT_PREFIXES = ("gh:", "gl:", "git+", "https://", "http://", "ssh://", "git@", "file://")
_PACK_KEYS = frozenset({"contract", "id", "name", "description", "version"})


@dataclass(frozen=True)
class TemplateSource:
    """Where a project's templates came from, as recorded in its manifest."""

    kind: str
    location: str
    ref: str | None = None
    pack_id: str | None = None
    pack_version: str | None = None

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


def _clone(location: str, ref: str | None, destination: Path) -> None:
    git = shutil.which("git")
    if git is None:
        raise PackError(f"git is required to use the template pack '{location}'; install git.")
    command = [git, "clone", "--quiet", "--depth", "1"]
    if ref:
        command += ["--branch", ref]
    url = _clone_url(location)
    if Path(url).is_dir():
        url = Path(url).resolve().as_uri()
    completed = subprocess.run(
        [*command, url, str(destination)], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise PackError(
            f"Could not clone template pack '{location}'"
            f"{f' at {ref}' if ref else ''}: {completed.stderr.strip()}"
        )
    # Render from a plain checkout; the source and ref are recorded separately.
    _remove_tree(destination / ".git")


def _make_writable_and_retry(function: Any, path: str, _: object) -> None:
    """Remove read-only git objects on Windows."""
    os.chmod(path, stat.S_IWRITE)
    function(path)


def _remove_tree(path: Path) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=_make_writable_and_retry)


def _check_safe(root: Path) -> None:
    """Reject symlinks (Copier would copy their targets) and code-running Copier settings."""
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PackError(
                f"Template pack contains a symlink, which is not allowed: {path.relative_to(root)}"
            )
    for config in [*root.glob("*.yml"), *root.glob("*.yaml")]:
        match = _UNSAFE_SETTINGS.search(config.read_text(encoding="utf-8"))
        if match:
            raise PackError(
                f"Template pack file {config.name} declares '{match.group(1)}', which "
                "pytemplate never runs; remove it from the pack."
            )


def _read_pack(root: Path) -> tuple[str, str]:
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
    return str(data["id"]), str(data["version"])


@contextmanager
def open_bundled_catalog_at(location: str, ref: str) -> Iterator[Catalog]:
    """Yield the bundled catalog as it was at ``ref`` of its git source (for updates)."""
    with tempfile.TemporaryDirectory(prefix="pytemplate-ref-") as scratch:
        root = Path(scratch) / "source"
        _clone(location, ref, root)
        package = root / "pytemplate"
        try:
            yield load_catalog(package / "templates", package / "components")
        except ManifestError as error:
            raise PackError(
                f"The templates at {ref} do not follow factory contract {CONTRACT_VERSION}: {error}"
            ) from error


@contextmanager
def open_catalog(
    template: str | None = None, ref: str | None = None, *, bundled_location: str = ""
) -> Iterator[tuple[Catalog, TemplateSource, Path]]:
    """Yield the catalog, its recorded source, and a local Copier template directory.

    ``template=None`` selects the bundled templates. Otherwise ``template`` is a local pack
    directory or a git source (``gh:org/repo``, a URL, or a local repository with ``ref``);
    git sources are cloned into a temporary directory that is removed afterwards.
    """
    if template is None:
        catalog = bundled_catalog()
        with resources.as_file(catalog.root) as root:
            yield catalog, TemplateSource(kind=BUNDLED, location=bundled_location, ref=ref), root
        return

    with tempfile.TemporaryDirectory(prefix="pytemplate-pack-") as scratch:
        if is_git_source(template) or ref:
            root = Path(scratch) / "pack"
            _clone(template, ref, root)
            location = template
        else:
            root = Path(template).expanduser().resolve()
            if not root.is_dir():
                raise PackError(f"Template pack directory does not exist: {root}")
            location = str(root)
        _check_safe(root)
        pack_id, pack_version = _read_pack(root)
        try:
            catalog = load_catalog(root, root / "components")
        except ManifestError as error:
            raise PackError(f"Template pack '{pack_id}': {error}") from error
        source = TemplateSource(
            kind="pack", location=location, ref=ref, pack_id=pack_id, pack_version=pack_version
        )
        yield catalog, source, root
