"""A unit of work on one SQLAlchemy session: commit keeps changes, leaving rolls back."""

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .repository import SqlExampleRepository


class SqlUnitOfWork:
    """Open a session on enter and close it on exit, rolling back uncommitted work."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._examples: SqlExampleRepository | None = None

    @property
    def examples(self) -> SqlExampleRepository:
        """Return the repository bound to this unit of work's session."""
        if self._examples is None:
            raise RuntimeError("Use the unit of work inside `async with`.")
        return self._examples

    async def __aenter__(self) -> Self:
        """Open a session."""
        self._session = self._session_factory()
        self._examples = SqlExampleRepository(self._session)
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Roll back anything uncommitted and close the session."""
        if self._session is not None:
            await self._session.rollback()
            await self._session.close()
        self._session = None
        self._examples = None

    async def commit(self) -> None:
        """Commit the session's changes."""
        if self._session is None:
            raise RuntimeError("Use the unit of work inside `async with`.")
        await self._session.commit()
