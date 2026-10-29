"""Errors the domain and use cases raise; the HTTP layer maps them to status codes."""

from typing import Any


class DomainError(Exception):
    """Base class for expected, domain-level failures."""

    code = "DOMAIN_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details


class NotFoundError(DomainError):
    """A requested entity does not exist."""

    code = "NOT_FOUND"

    def __init__(self, entity: str, identifier: object) -> None:
        super().__init__(
            f"{entity} {identifier} was not found", {"entity": entity, "id": str(identifier)}
        )


class InvalidValueError(DomainError):
    """A value breaks a domain rule."""

    code = "INVALID_VALUE"
