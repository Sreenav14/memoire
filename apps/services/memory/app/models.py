import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector 
from sqlalchemy import Text, DateTime
import datetime
from sqlalchemy.sql import func

from .database import Base

class UserSpace(Base):
    __tablename__ = "user_spaces"
    
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    space_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
class MemoryItem(Base):
    __tablename__ = "memory_items"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    space_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False) 
    
    type: Mapped[str] = mapped_column(Text, nullable=False) # note / decision
    content: Mapped[str] = mapped_column(Text, nullable=False)
    emb_text: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
