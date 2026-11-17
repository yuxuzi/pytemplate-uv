"""PyTemplate's deterministic project-factory package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pytemplate-uv")
except PackageNotFoundError:
    __version__ = "uninstalled"

__all__ = ["__version__"]
