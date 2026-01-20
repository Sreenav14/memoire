from pydantic import BaseModel, Field
from uuid import UUID

class NoteCreate(BaseModel):
    space_id: UUID
    content: str = Field(min_length=1, max_length=10000)
    