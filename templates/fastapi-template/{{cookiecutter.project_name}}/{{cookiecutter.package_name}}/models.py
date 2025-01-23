from sqlmodel import SQLModel, Field
from typing import Optional

class ExampleModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, description="Name cannot be an empty string")
    description: str
