"""`ExampleRepository` on an SQLAlchemy async session."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.examples import Example, NewExample
from .models import ExampleRow


def _aware(value: datetime) -> datetime:
    """SQLite drops time zones; every stored time is UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _to_domain(row: ExampleRow) -> Example:
    return Example(
        id=row.id,
        name=row.name,
        description=row.description,
        is_active=row.is_active,
        tags=tuple(row.tags),
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at) if row.updated_at else None,
    )


class SqlExampleRepository:
    """Stores examples in the `examples` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, new: NewExample, *, created_at: datetime) -> Example:
        """Insert an example and return it with its identifier."""
        row = ExampleRow(
            name=new.name,
            description=new.description,
            is_active=True,
            tags=list(new.tags),
            created_at=created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def get(self, example_id: int) -> Example | None:
        """Return one example, or None."""
        row = await self._session.get(ExampleRow, example_id)
        return _to_domain(row) if row else None

    async def page(self, *, offset: int, limit: int) -> list[Example]:
        """Return examples in identifier order."""
        rows = await self._session.scalars(
            select(ExampleRow).order_by(ExampleRow.id).offset(offset).limit(limit)
        )
        return [_to_domain(row) for row in rows]

    async def save(self, example: Example) -> None:
        """Replace the stored fields of an example."""
        row = await self._session.get(ExampleRow, example.id)
        if row is None:
            return
        row.name = example.name
        row.description = example.description
        row.is_active = example.is_active
        row.tags = list(example.tags)
        row.updated_at = example.updated_at
        await self._session.flush()

    async def delete(self, example_id: int) -> None:
        """Delete an example if it exists."""
        row = await self._session.get(ExampleRow, example_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def count(self) -> int:
        """Return how many examples are stored."""
        return int(await self._session.scalar(select(func.count()).select_from(ExampleRow)) or 0)
