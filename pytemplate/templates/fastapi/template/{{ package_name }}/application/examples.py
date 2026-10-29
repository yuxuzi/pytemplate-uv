"""Example use cases."""

from collections.abc import Callable
from datetime import UTC, datetime

from ..domain.errors import NotFoundError
from ..domain.examples import Example, ExampleChanges, NewExample
from ..domain.ports import UnitOfWork


def utcnow() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


class ExampleService:
    """Create, read, update, and delete examples within one unit of work."""

    def __init__(self, unit_of_work: UnitOfWork, clock: Callable[[], datetime] = utcnow) -> None:
        self._uow = unit_of_work
        self._clock = clock

    async def create(self, new: NewExample) -> Example:
        """Store a new example."""
        example = await self._uow.examples.add(new, created_at=self._clock())
        await self._uow.commit()
        return example

    async def get(self, example_id: int) -> Example:
        """Return one example or raise `NotFoundError`."""
        example = await self._uow.examples.get(example_id)
        if example is None:
            raise NotFoundError("Example", example_id)
        return example

    async def page(self, offset: int, limit: int) -> list[Example]:
        """Return one page of examples."""
        return await self._uow.examples.page(offset=offset, limit=limit)

    async def update(self, example_id: int, changes: ExampleChanges) -> Example:
        """Apply a partial update."""
        updated = (await self.get(example_id)).apply(changes, self._clock())
        await self._uow.examples.save(updated)
        await self._uow.commit()
        return updated

    async def delete(self, example_id: int) -> None:
        """Delete an example or raise `NotFoundError`."""
        await self.get(example_id)
        await self._uow.examples.delete(example_id)
        await self._uow.commit()

    async def count(self) -> int:
        """Return the number of stored examples."""
        return await self._uow.examples.count()
