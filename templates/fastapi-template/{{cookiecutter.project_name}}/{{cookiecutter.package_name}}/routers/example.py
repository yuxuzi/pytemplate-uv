from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.exceptions import NotFoundError, ValidationError
from ..db import async_session
from ..models import ExampleModel

router = APIRouter()

async def get_db():
    """Dependency for database session."""
    async with async_session() as session:
        yield session

@router.get("/examples/", response_model=List[ExampleModel])
async def list_examples(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of items to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all examples with pagination.
    
    Args:
        skip: Number of items to skip for pagination
        limit: Maximum number of items to return
        db: Database session
    
    Returns:
        List of example items
    """
    query = select(ExampleModel).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/examples/{example_id}", response_model=ExampleModel)
async def get_example(example_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get a specific example by ID.
    
    Args:
        example_id: ID of the example to retrieve
        db: Database session
    
    Returns:
        Example item
    
    Raises:
        NotFoundError: If example with given ID doesn't exist
    """
    result = await db.get(ExampleModel, example_id)
    if not result:
        raise NotFoundError("Example", example_id)
    return result

@router.post("/examples/", response_model=ExampleModel)
async def create_example(example: ExampleModel, db: AsyncSession = Depends(get_db)):
    """
    Create a new example.
    
    Args:
        example: Example data to create
        db: Database session
    
    Returns:
        Created example item
    
    Raises:
        ValidationError: If example data is invalid
    """
    try:
        db.add(example)
        await db.commit()
        await db.refresh(example)
        return example
    except Exception as e:
        raise ValidationError(str(e))

@router.delete("/examples/{example_id}")
async def delete_example(example_id: int, db: AsyncSession = Depends(get_db)):
    """
    Delete an example by ID.
    
    Args:
        example_id: ID of the example to delete
        db: Database session
    
    Returns:
        Success message
    
    Raises:
        NotFoundError: If example with given ID doesn't exist
    """
    example = await db.get(ExampleModel, example_id)
    if not example:
        raise NotFoundError("Example", example_id)
    
    await db.delete(example)
    await db.commit()
    
    return {"message": f"Example {example_id} deleted successfully"}
