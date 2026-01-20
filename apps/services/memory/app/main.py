from fastapi import FastAPI, HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from sqlalchemy import select
from uuid import UUID

from .deps import get_db
from .models import UserSpace, MemoryItem
from .schema import NoteCreate
from .auth_deps import get_current_user
from .routers import notes

load_dotenv()
app = FastAPI(title="Memoire memory service", version="0.1.0")

@app.get("/health")
def health():
    return {"status":"ok", "service":"memoire-memory"}

app.include_router(notes.router)