"""API-key authentication for service-to-service calls (header `X-API-Key`)."""

import hashlib
import hmac
from collections.abc import Sequence

from fastapi import Request

from ..bootstrap.settings import ApiKey
from .principal import AuthenticationError, Principal

API_KEY_HEADER = "X-API-Key"


def hash_api_key(key: str) -> str:
    """Return the SHA-256 hex digest that API_KEYS stores instead of the key."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class ApiKeyAuthenticator:
    """Accept a request whose key hashes to a configured entry."""

    def __init__(self, keys: Sequence[ApiKey]) -> None:
        self._keys = tuple(keys)

    async def authenticate(self, request: Request) -> Principal:
        """Return the client the key belongs to, or raise `AuthenticationError`."""
        presented = request.headers.get(API_KEY_HEADER)
        if not presented:
            raise AuthenticationError(f"Missing {API_KEY_HEADER} header.", scheme="ApiKey")
        digest = hash_api_key(presented)
        match: ApiKey | None = None
        for key in self._keys:  # compare with every key so timing does not reveal which matched
            if hmac.compare_digest(digest, key.sha256):
                match = key
        if match is None:
            raise AuthenticationError("Invalid API key.", scheme="ApiKey")
        return Principal(subject=match.name, scopes=frozenset(match.scopes))
