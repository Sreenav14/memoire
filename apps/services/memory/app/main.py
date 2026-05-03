from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import time
import logging

from .routers import notes
from .routers import search
from .routers import chats
from .routers import chat_save
from .routers import documents
from .routers import profile
from .routers import inference_rules

load_dotenv()

SERVICE_NAME = os.getenv("SERVICE_NAME", "memoire-memory")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.1")
DEBUG = os.getenv("DEBUG", "0") == "1"

log = logging.getLogger("memoire.memory")

app = FastAPI(title=f"Memoire {SERVICE_NAME}", version=SERVICE_VERSION, debug=DEBUG)

# Optional CORS
allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS")
if allowed_origins:
    origins = [o.strip() for o in allowed_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

START_TIME = time.time()


@app.on_event("startup")
def _startup():
    log.info("%s starting (version=%s) debug=%s", SERVICE_NAME, SERVICE_VERSION, DEBUG)


@app.on_event("shutdown")
def _shutdown():
    log.info("%s shutting down", SERVICE_NAME)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "uptime_seconds": int(time.time() - START_TIME),
    }


app.include_router(notes.router)
app.include_router(search.router)
app.include_router(chats.router)
app.include_router(chat_save.router)
app.include_router(documents.router)
app.include_router(profile.router)
app.include_router(inference_rules.router)