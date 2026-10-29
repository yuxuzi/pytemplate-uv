"""Ports: the interfaces the use cases need. Adapters in `infrastructure` implement them."""

from datetime import datetime
from typing import Protocol, Self

from .examples import Example, NewExample


class ExampleRepository(Protocol):
    """Stores and finds examples."""

    async def add(self, new: NewExample, *, created_at: datetime) -> Example:
        """Store a new example and return it with its identifier."""
        ...

    async def get(self, example_id: int) -> Example | None:
        """Return one example, or None."""
        ...

    async def page(self, *, offset: int, limit: int) -> list[Example]:
        """Return examples in identifier order."""
        ...

    async def save(self, example: Example) -> None:
        """Replace a stored example."""
        ...

    async def delete(self, example_id: int) -> None:
        """Remove an example; a missing one is ignored."""
        ...

    async def count(self) -> int:
        """Return how many examples are stored."""
        ...


class UnitOfWork(Protocol):
    """One atomic set of changes: commit to keep them, or leave to roll them back."""

    @property
    def examples(self) -> ExampleRepository:
        """Return the example repository bound to this unit of work."""
        ...

    async def __aenter__(self) -> Self:
        """Start the unit of work."""
        ...

    async def __aexit__(self, *exc_info: object) -> None:
        """Roll back anything not committed."""
        ...

    async def commit(self) -> None:
        """Make the changes durable."""
        ...
