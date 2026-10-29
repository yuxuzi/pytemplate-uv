"""Request and response bodies; they are separate from the domain model on purpose."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..domain.examples import Example


class ExampleCreate(BaseModel):
    """Request body for creating an example."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=20)


class ExampleUpdate(BaseModel):
    """Request body for a partial update; omitted fields stay unchanged."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    is_active: bool | None = None
    tags: list[str] | None = Field(default=None, max_length=20)


class ExampleRead(BaseModel):
    """Response body for an example."""

    id: int
    name: str
    description: str
    is_active: bool
    tags: list[str]
    created_at: datetime
    updated_at: datetime | None

    @classmethod
    def from_domain(cls, example: Example) -> "ExampleRead":
        """Convert a domain entity into its public representation."""
        return cls(
            id=example.id,
            name=example.name,
            description=example.description,
            is_active=example.is_active,
            tags=list(example.tags),
            created_at=example.created_at,
            updated_at=example.updated_at,
        )
