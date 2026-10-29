"""The principal model, the authenticator port, and authentication errors."""

from dataclasses import dataclass
from typing import Protocol

from fastapi import Request, status

from ..api.errors import ApiError


@dataclass(frozen=True)
class Principal:
    """An authenticated caller and the scopes it was granted."""

    subject: str
    scopes: frozenset[str] = frozenset()

    def missing(self, required: frozenset[str]) -> frozenset[str]:
        """Return the required scopes this principal lacks."""
        return required - self.scopes


class Authenticator(Protocol):
    """Turns request credentials into a `Principal`; implemented once per mode."""

    async def authenticate(self, request: Request) -> Principal:
        """Return the caller, or raise `AuthenticationError`."""
        ...


class AuthenticationError(ApiError):
    """Missing or invalid credentials (401)."""

    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHENTICATED"

    def __init__(self, message: str, scheme: str) -> None:
        super().__init__(message, headers={"WWW-Authenticate": scheme})


class AuthorizationError(ApiError):
    """Valid credentials without the required scopes (403)."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
