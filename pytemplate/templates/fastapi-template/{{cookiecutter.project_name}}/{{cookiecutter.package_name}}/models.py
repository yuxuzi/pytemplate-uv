from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, JSON, Column
from pydantic import ConfigDict


class ExampleModel(SQLModel, table=True):
    """Example model with modern SQLModel practices for version 2.0."""
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )
    
    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Required fields with validation
    name: str = Field(
        min_length=1, 
        max_length=100,
        description="Name cannot be an empty string"
    )
    
    description: str = Field(
        min_length=1,
        max_length=500,
        description="Description of the example"
    )
    
    # Optional fields
    is_active: bool = Field(default=True, description="Whether the example is active")
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(JSON), description="Tags for categorization")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)


class ExampleCreate(SQLModel):
    """Schema for creating an example."""
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    is_active: bool = Field(default=True)
    tags: Optional[List[str]] = Field(default=None)


class ExampleUpdate(SQLModel):
    """Schema for updating an example."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, min_length=1, max_length=500)
    is_active: Optional[bool] = Field(default=None)
    tags: Optional[List[str]] = Field(default=None)


class ExampleResponse(SQLModel):
    """Schema for example responses."""
    id: int
    name: str
    description: str
    is_active: bool
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: Optional[datetime]
