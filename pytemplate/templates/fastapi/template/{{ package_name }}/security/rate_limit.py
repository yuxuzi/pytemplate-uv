"""A rate-limit seam: the dependency is wired in; the default limiter allows everything."""

from typing import Protocol

from fastapi import status

from ..api.errors import ApiError


class RateLimiter(Protocol):
    """Decides whether a caller may make another request now."""

    async def allow(self, key: str) -> bool:
        """Return False to reject the request with 429."""
        ...


class NoRateLimit:
    """Allow every request; replace with a shared-store limiter before relying on limits."""

    async def allow(self, key: str) -> bool:
        """Always allow."""
        return True


class RateLimitedError(ApiError):
    """Too many requests (429)."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "TOO_MANY_REQUESTS"
