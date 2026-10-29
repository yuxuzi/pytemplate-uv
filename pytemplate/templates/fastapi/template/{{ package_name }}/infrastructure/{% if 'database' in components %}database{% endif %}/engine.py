"""The engine and session factory, built from the configured URL; nothing connects early."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .unit_of_work import SqlUnitOfWork


class Database:
    """Owns the engine for one application."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.engine = create_async_engine(url, echo=echo, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    def unit_of_work(self) -> SqlUnitOfWork:
        """Return a new unit of work."""
        return SqlUnitOfWork(self.session_factory)

    async def ping(self) -> None:
        """Readiness check: run a trivial query."""
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        """Close every pooled connection."""
        await self.engine.dispose()
