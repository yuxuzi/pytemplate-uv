"""Error types shared by the rendering, pack, and update modules."""

from __future__ import annotations


class RenderError(RuntimeError):
    """Raised when a validated render request cannot be completed (CLI exit code 2)."""


class RequestError(RenderError):
    """Raised when a render request is invalid and nothing was written (CLI exit code 1)."""


class PackError(RequestError):
    """Raised when an external template pack cannot be used safely."""
