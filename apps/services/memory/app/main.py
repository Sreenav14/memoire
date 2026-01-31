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
from .routers import search
from .routers import chats
from .routers import chat_save
from .routers import documents

load_dotenv()
app = FastAPI(title="Memoire memory service", version="0.1.0", debug=True)

@app.get("/health")
def health():
    return {"status":"ok", "service":"memoire-memory"}

app.include_router(notes.router)
app.include_router(search.router)
app.include_router(chats.router)
app.include_router(chat_save.router)
app.include_router(documents.router)