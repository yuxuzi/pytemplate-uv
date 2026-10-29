"""The example entity, its invariants, and the changes that may be applied to it."""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Self

from .errors import InvalidValueError

MAX_NAME_LENGTH = 100


def _check_name(name: str) -> None:
    if not name.strip() or len(name) > MAX_NAME_LENGTH:
        raise InvalidValueError(
            f"Example names must be 1 to {MAX_NAME_LENGTH} characters.", {"field": "name"}
        )


@dataclass(frozen=True)
class NewExample:
    """An example that has not been stored yet."""

    name: str
    description: str
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _check_name(self.name)


@dataclass(frozen=True)
class ExampleChanges:
    """A partial update; `None` means "leave unchanged"."""

    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    tags: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Example:
    """A stored example."""

    id: int
    name: str
    description: str
    is_active: bool
    tags: tuple[str, ...]
    created_at: datetime
    updated_at: datetime | None = None

    def apply(self, changes: ExampleChanges, now: datetime) -> Self:
        """Return a copy with the given changes and a new `updated_at`."""
        if changes.name is not None:
            _check_name(changes.name)
        updates = {key: value for key, value in vars(changes).items() if value is not None}
        return replace(self, **updates, updated_at=now)
