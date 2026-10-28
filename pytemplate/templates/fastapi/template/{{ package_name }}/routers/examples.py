"""CRUD endpoints for examples."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.exceptions import NotFoundError
from ..db import get_session
from ..models import Example, ExampleCreate, ExampleRead, ExampleUpdate, utcnow

router = APIRouter(prefix="/examples", tags=["examples"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _get_or_404(session: AsyncSession, example_id: int) -> Example:
    example = await session.get(Example, example_id)
    if example is None:
        raise NotFoundError("Example", example_id)
    return example


@router.get("/", response_model=list[ExampleRead])
async def list_examples(
    session: SessionDep,
    skip: Annotated[int, Query(ge=0, description="Number of items to skip")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum items to return")] = 10,
) -> Sequence[Example]:
    """List examples in creation order."""
    result = await session.exec(select(Example).order_by(col(Example.id)).offset(skip).limit(limit))
    return result.all()


@router.post("/", response_model=ExampleRead, status_code=status.HTTP_201_CREATED)
async def create_example(payload: ExampleCreate, session: SessionDep) -> Example:
    """Create an example."""
    example = Example.model_validate(payload)
    session.add(example)
    await session.commit()
    await session.refresh(example)
    return example


@router.get("/{example_id}", response_model=ExampleRead)
async def get_example(example_id: int, session: SessionDep) -> Example:
    """Return one example."""
    return await _get_or_404(session, example_id)


@router.patch("/{example_id}", response_model=ExampleRead)
async def update_example(example_id: int, payload: ExampleUpdate, session: SessionDep) -> Example:
    """Update the provided fields of an example."""
    example = await _get_or_404(session, example_id)
    example.sqlmodel_update(payload.model_dump(exclude_unset=True))
    example.updated_at = utcnow()
    session.add(example)
    await session.commit()
    await session.refresh(example)
    return example


@router.delete("/{example_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_example(example_id: int, session: SessionDep) -> None:
    """Delete an example."""
    example = await _get_or_404(session, example_id)
    await session.delete(example)
    await session.commit()
