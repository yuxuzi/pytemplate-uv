"""In-memory adapters: the default storage, and fakes for use-case tests."""

from dataclasses import replace
from datetime import datetime
from typing import Self

from ..domain.examples import Example, NewExample


class InMemoryExampleStore:
    """Process-local storage shared by every unit of work of one application."""

    def __init__(self) -> None:
        self.rows: dict[int, Example] = {}
        self.next_id = 1


class InMemoryExampleRepository:
    """An `ExampleRepository` over a private working copy of the store."""

    def __init__(self, rows: dict[int, Example], next_id: int) -> None:
        self.rows = rows
        self.next_id = next_id

    async def add(self, new: NewExample, *, created_at: datetime) -> Example:
        """Store a new example."""
        example = Example(
            id=self.next_id,
            name=new.name,
            description=new.description,
            is_active=True,
            tags=new.tags,
            created_at=created_at,
        )
        self.rows[example.id] = example
        self.next_id += 1
        return example

    async def get(self, example_id: int) -> Example | None:
        """Return one example, or None."""
        return self.rows.get(example_id)

    async def page(self, *, offset: int, limit: int) -> list[Example]:
        """Return examples in identifier order."""
        return [self.rows[key] for key in sorted(self.rows)][offset : offset + limit]

    async def save(self, example: Example) -> None:
        """Replace a stored example."""
        self.rows[example.id] = replace(example)

    async def delete(self, example_id: int) -> None:
        """Remove an example."""
        self.rows.pop(example_id, None)

    async def count(self) -> int:
        """Return how many examples are stored."""
        return len(self.rows)


class InMemoryUnitOfWork:
    """Stage changes on a copy and publish them to the store on commit."""

    def __init__(self, store: InMemoryExampleStore) -> None:
        self._store = store
        self.examples = InMemoryExampleRepository(dict(store.rows), store.next_id)
        self.committed = False

    async def __aenter__(self) -> Self:
        """Start from the store's current contents."""
        self.examples = InMemoryExampleRepository(dict(self._store.rows), self._store.next_id)
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Discard anything not committed."""

    async def commit(self) -> None:
        """Publish the staged changes."""
        self._store.rows = dict(self.examples.rows)
        self._store.next_id = self.examples.next_id
        self.committed = True
