from pydantic import BaseModel, Field
from uuid import UUID
from typing import List, Optional, Any, Dict, Literal

class NoteCreate(BaseModel):
    space_id: UUID
    content: str = Field(min_length=1, max_length=10000)
    
class ChatRequest(BaseModel):
    space_id: UUID
    message: str
    k: int  = 8
    provider: Literal["openai", "groq"] = "openai"
    model: Optional[str] = None
    
class MemoryCitation(BaseModel):
    id: str
    score: float
    created_at: Any
    snippet: str
    
class ChatResponse(BaseModel):
    answer: str
    memory_used: List[MemoryCitation]
    
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

SaveMode= Literal["last_assistant", "last_user","full"]

class SaveConversationRequest(BaseModel):
    space_id: UUID
    messages: List[ChatMessage]
    mode: SaveMode
    title: Optional[str] = None
    max_message: Optional[int] = 20  #used for 'full'

class DocumentCreate(BaseModel):
    space_id: UUID
    source_type: str = Field(default="upload")
    title: Optional[str] = None
    source_url: Optional[str] = None
    text: Optional[str] = None
    
class DocumentOut(BaseModel):
    id: UUID
    space_id: UUID
    user_id: UUID
    source_type: str
    title: Optional[str] = None
    source_url: Optional[str] = None
    status: str
    created_at: str