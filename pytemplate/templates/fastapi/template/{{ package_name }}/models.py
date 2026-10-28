"""Database models and API schemas."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


class ExampleBase(SQLModel):
    """Fields shared by the table model and the API schemas."""

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    is_active: bool = True
    tags: list[str] | None = None


class Example(ExampleBase, table=True):
    """Persisted example record."""

    id: int | None = Field(default=None, primary_key=True)
    tags: list[str] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime | None = None


class ExampleCreate(ExampleBase):
    """Request body for creating an example."""


class ExampleUpdate(SQLModel):
    """Request body for a partial update; omitted fields are left unchanged."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    is_active: bool | None = None
    tags: list[str] | None = None


class ExampleRead(ExampleBase):
    """Response body for an example."""

    id: int
    created_at: datetime
    updated_at: datetime | None
