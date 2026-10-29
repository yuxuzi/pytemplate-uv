"""OpenID Connect bearer-token authentication: JWT signature, issuer, audience, and expiry."""

import asyncio
from collections.abc import Callable, Sequence
from typing import Any, Self

import jwt
from fastapi import Request

from ..bootstrap.settings import Settings
from .principal import AuthenticationError, Principal

KeyResolver = Callable[[str], Any]


def _scopes(claims: dict[str, Any]) -> frozenset[str]:
    """Read OAuth2 scopes from `scope` (space-separated) or `scp` (a list)."""
    scope = claims.get("scope")
    if isinstance(scope, str):
        return frozenset(scope.split())
    scp = claims.get("scp")
    return frozenset(str(item) for item in scp) if isinstance(scp, list) else frozenset()


class OidcAuthenticator:
    """Validate `Authorization: Bearer <JWT>` against the provider's signing keys."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        algorithms: Sequence[str],
        key_for_token: KeyResolver,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._algorithms = list(algorithms)
        self._key_for_token = key_for_token

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        """Fetch signing keys from OIDC_JWKS_URL lazily, on the first request that needs one."""
        client = jwt.PyJWKClient(settings.OIDC_JWKS_URL) if settings.OIDC_JWKS_URL else None

        def key_for_token(token: str) -> Any:
            if client is None:
                raise jwt.InvalidTokenError("OIDC_JWKS_URL is not configured.")
            return client.get_signing_key_from_jwt(token).key

        return cls(
            issuer=settings.OIDC_ISSUER,
            audience=settings.OIDC_AUDIENCE,
            algorithms=settings.OIDC_ALGORITHMS,
            key_for_token=key_for_token,
        )

    async def authenticate(self, request: Request) -> Principal:
        """Return the token's subject and scopes, or raise `AuthenticationError`."""
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise AuthenticationError("Missing bearer token.", scheme="Bearer")
        try:
            key = await asyncio.to_thread(self._key_for_token, token)
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as error:
            raise AuthenticationError(
                "Invalid bearer token.", scheme='Bearer error="invalid_token"'
            ) from error
        return Principal(subject=str(claims["sub"]), scopes=_scopes(claims))
