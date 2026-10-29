"""Example endpoints. Handlers only translate HTTP to use cases and back."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from ...domain.examples import ExampleChanges, NewExample
from ..dependencies import ExampleServiceDep
from ..schemas import ExampleCreate, ExampleRead, ExampleUpdate

# Two routers so the application can protect reads and writes differently.
read_router = APIRouter(prefix="/examples", tags=["examples"])
write_router = APIRouter(prefix="/examples", tags=["examples"])


@read_router.get("")
async def list_examples(
    service: ExampleServiceDep,
    offset: Annotated[int, Query(ge=0, description="Number of items to skip")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum items to return")] = 20,
) -> list[ExampleRead]:
    """List examples in creation order."""
    return [ExampleRead.from_domain(item) for item in await service.page(offset, limit)]


@read_router.get("/{example_id}")
async def get_example(example_id: int, service: ExampleServiceDep) -> ExampleRead:
    """Return one example."""
    return ExampleRead.from_domain(await service.get(example_id))


@write_router.post("", status_code=status.HTTP_201_CREATED)
async def create_example(payload: ExampleCreate, service: ExampleServiceDep) -> ExampleRead:
    """Create an example."""
    created = await service.create(
        NewExample(name=payload.name, description=payload.description, tags=tuple(payload.tags))
    )
    return ExampleRead.from_domain(created)


@write_router.patch("/{example_id}")
async def update_example(
    example_id: int, payload: ExampleUpdate, service: ExampleServiceDep
) -> ExampleRead:
    """Update the provided fields of an example."""
    fields = payload.model_dump(exclude_unset=True)
    if "tags" in fields and fields["tags"] is not None:
        fields["tags"] = tuple(fields["tags"])
    updated = await service.update(example_id, ExampleChanges(**fields))
    return ExampleRead.from_domain(updated)


@write_router.delete("/{example_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_example(example_id: int, service: ExampleServiceDep) -> None:
    """Delete an example."""
    await service.delete(example_id)
