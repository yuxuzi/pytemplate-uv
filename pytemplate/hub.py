"""Pins for a pack listed on pytemplate-hub, read from the hub's index with the standard library.

The hub is only a lookup: it supplies the repository, tag, commit, and digest that the pinned
git path already checks. A moved tag or changed files are refused there, as with the full command.
"""

from __future__ import annotations

import os
import re
import tomllib
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pytemplate.errors import RequestError
from pytemplate.packs import _git_timeout

HUB_URL_ENV = "PYTEMPLATE_HUB_URL"
DEFAULT_HUB_INDEX = "https://raw.githubusercontent.com/yuxuzi/pytemplate-hub/main/index"
HUB_SITE = "https://yuxuzi.github.io/pytemplate-hub/"
_SPEC = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9-]*)/([a-z0-9][a-z0-9-]*)(?:@([A-Za-z0-9][A-Za-z0-9._-]*))?$"
)
_REPOSITORY = re.compile(r"^https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+)$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MAX_ENTRY_BYTES = 1024 * 1024


class HubError(RequestError):
    """Raised when a pack cannot be resolved through pytemplate-hub (CLI exit code 1)."""


@dataclass(frozen=True)
class HubPin:
    """One listed version of a hub pack, with the pins the pinned git path verifies."""

    pack: str
    repository: str
    tag: str
    commit: str
    digest: str
    reviewed_by: str | None = None
    profile_lifecycles: Mapping[str, str] = field(default_factory=dict)

    @property
    def location(self) -> str:
        """Return the git template location, in the short form the manifest records."""
        return "gh:" + self.repository.removeprefix("https://github.com/")

    @property
    def notice(self) -> str:
        """Return the one line that says what was resolved and how far it is trusted."""
        trust = (
            f"reviewed by {self.reviewed_by}"
            if self.reviewed_by
            else "listed on the hub, not reviewed"
        )
        return (
            f"Using {self.pack} {self.tag} (commit {self.commit[:7]}, digest {self.digest[:8]}…), "
            f"{trust}."
        )


def hub_index_url() -> str:
    """Return the hub index base URL, from ``PYTEMPLATE_HUB_URL`` or the public hub."""
    return (os.environ.get(HUB_URL_ENV) or DEFAULT_HUB_INDEX).rstrip("/")


def parse_spec(spec: str) -> tuple[str, str, str | None]:
    """Split ``OWNER/PACK[@TAG]`` into its parts, or raise ``HubError`` with an example."""
    match = _SPEC.match(spec)
    if match is None:
        raise HubError(
            f"--hub expects OWNER/PACK or OWNER/PACK@TAG, for example "
            f"yuxuzi/pytemplate-starters or yuxuzi/pytemplate-starters@v1.0.0, got '{spec}'."
        )
    owner, pack, tag = match.groups()
    return owner, pack, tag


def _read_entry(url: str, pack: str) -> bytes:
    """Fetch one hub entry of at most 1 MiB; a 404 (or a missing file URL) means not listed."""
    not_listed = HubError(
        f"'{pack}' is not listed on pytemplate-hub. Browse the listed packs at {HUB_SITE}, or "
        "pass --template for a pack that is not listed."
    )
    try:
        with urllib.request.urlopen(url, timeout=_git_timeout()) as response:
            data = bytes(response.read(_MAX_ENTRY_BYTES + 1))
        if len(data) > _MAX_ENTRY_BYTES:
            raise HubError(
                f"The pytemplate-hub entry for '{pack}' is larger than 1 MiB. Pass the full "
                "--template pins instead."
            )
        return data
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise not_listed from error
        raise HubError(
            f"Could not read the pytemplate-hub entry for '{pack}': HTTP {error.code}. Try again, "
            "or pass the full --template pins to work without the hub."
        ) from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, FileNotFoundError):
            raise not_listed from error
        raise HubError(
            f"Could not reach pytemplate-hub for '{pack}': {error.reason}. Check your network, or "
            "pass the full --template pins to work offline."
        ) from error
    except OSError as error:
        raise HubError(
            f"Could not read the pytemplate-hub entry for '{pack}': {error}. Check your network, "
            "or pass the full --template pins to work offline."
        ) from error


def _versions(raw: bytes, pack: str, owner: str) -> tuple[str, list[dict[str, Any]]]:
    """Return the entry's repository and versions after checking the fields this reads."""
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise HubError(
            f"The pytemplate-hub entry for '{pack}' is not valid TOML: {error}"
        ) from error
    if data.get("format") != 1:
        raise HubError(
            f"The pytemplate-hub entry for '{pack}' has format {data.get('format')!r}, which this "
            "pytemplate-uv does not read. Upgrade pytemplate-uv."
        )
    repository = data.get("repository")
    match = _REPOSITORY.match(repository) if isinstance(repository, str) else None
    if match is None or match.group(1).lower() != owner.lower():
        raise HubError(f"The pytemplate-hub entry for '{pack}' has no valid GitHub repository.")
    versions = data.get("versions", [])
    for version in versions:
        if not all(isinstance(version.get(key), str) for key in ("tag", "commit", "digest")):
            raise HubError(
                f"A version of '{pack}' on pytemplate-hub lacks its tag, commit, or digest."
            )
        if not _COMMIT.match(version["commit"]) or not _DIGEST.match(version["digest"]):
            raise HubError(
                f"A version of '{pack}' on pytemplate-hub has a malformed commit or digest."
            )
    return str(repository), list(versions)


def _newest(versions: list[dict[str, Any]], pack: str) -> dict[str, Any]:
    """Return the most recently listed version that is not yanked."""
    active = [version for version in versions if version.get("yanked") is None]
    if not active:
        raise HubError(f"'{pack}' has no version on pytemplate-hub that is not yanked.")
    return active[-1]


def _select(versions: list[dict[str, Any]], tag: str | None, pack: str) -> dict[str, Any]:
    """Pick the requested tag, or the newest version that is not yanked."""
    if tag is None:
        return _newest(versions, pack)
    matches = [version for version in versions if version["tag"] == tag]
    if not matches:
        listed = ", ".join(version["tag"] for version in versions) or "none"
        raise HubError(f"Tag '{tag}' is not listed for '{pack}'. Listed tags: {listed}.")
    version = matches[0]
    if version.get("yanked") is not None:
        newest = _newest(versions, pack)["tag"]
        raise HubError(
            f"Tag '{tag}' of '{pack}' is yanked on pytemplate-hub ({version['yanked']}). "
            f"The newest version that is not yanked is {newest}: pass --hub {pack}@{newest}, "
            "or omit @TAG."
        )
    return version


def lookup_hub(spec: str) -> HubPin:
    """Resolve ``OWNER/PACK[@TAG]`` to the listed pins, fetching the hub's entry once."""
    owner, pack, tag = parse_spec(spec)
    name = f"{owner.lower()}/{pack}"
    raw = _read_entry(f"{hub_index_url()}/{owner.lower()}/{pack}.toml", name)
    repository, versions = _versions(raw, name, owner)
    version = _select(versions, tag, name)
    reviewed = version.get("reviewed_by")
    return HubPin(
        pack=name,
        repository=repository,
        tag=version["tag"],
        commit=version["commit"],
        digest=version["digest"],
        reviewed_by=reviewed if isinstance(reviewed, str) else None,
        profile_lifecycles=_lifecycles(version),
    )


def _lifecycles(version: dict[str, Any]) -> dict[str, str]:
    """Return each profile's lifecycle result (``passed`` or ``not-run``) from the entry."""
    profiles = version.get("profiles", [])
    if not isinstance(profiles, list):
        return {}
    return {
        item["id"]: item["lifecycle"]
        for item in profiles
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("lifecycle"), str)
    }


def pin_for(
    spec: str,
    *,
    template: str | None,
    template_ref: str | None,
    template_commit: str | None,
    template_digest: str | None,
) -> HubPin:
    """Resolve ``--hub`` after refusing any template flag, which would be a second source."""
    if any(
        value is not None for value in (template, template_ref, template_commit, template_digest)
    ):
        raise HubError(
            "--hub names the pack and its pins; drop --template, --template-ref, "
            "--template-commit, and --template-digest."
        )
    return lookup_hub(spec)
