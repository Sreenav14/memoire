from fastapi import FastAPI
from dotenv import load_dotenv

from .routers import notes
from .routers import search
from .routers import chats
from .routers import chat_save
from .routers import documents
from .routers import profile
from .routers import inference_rules

load_dotenv()
app = FastAPI(title="Memoire memory service", version="0.1.0", debug=True)


@app.get("/health")
def health():
    return {"status": "ok", "service": "memoire-memory"}


app.include_router(notes.router)
app.include_router(search.router)
app.include_router(chats.router)
app.include_router(chat_save.router)
app.include_router(documents.router)
app.include_router(profile.router)
app.include_router(inference_rules.router)