from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
import datetime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
import uuid

from .db import Base

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    spaces: Mapped[list["UserSpace"]] = relationship("UserSpace",back_populates="user")
    
class Space(Base):
    __tablename__ = "spaces"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key = True, default = uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    members: Mapped[list["UserSpace"]] = relationship("UserSpace", back_populates="space")

    
class UserSpace(Base):
    __tablename__ = "user_spaces"
    
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    space_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spaces.id",ondelete="CASCADE"), primary_key=True)
    
    role: Mapped[str] = mapped_column(String, default="owner", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    user: Mapped["User"] = relationship("User", back_populates="spaces")
    space: Mapped["Space"] = relationship("Space", back_populates="members")

class UserPassword(Base):
    __tablename__ = "user_passwords"
    
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(User.id, ondelete="CASCADE"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    
    user: Mapped["User"] = relationship("User")
    