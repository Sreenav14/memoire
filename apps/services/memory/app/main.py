from fastapi import FastAPI
from dotenv import load_dotenv
import os
import time
import sys
import platform
from typing import Any

from .routers import notes
from .routers import search
from .routers import chats
from .routers import chat_save
from .routers import documents
from .routers import profile
from .routers import inference_rules

load_dotenv()
START_TIME = time.time()
app = FastAPI(title="Memoire memory service", version="2.1.0", debug=True)


@app.get("/health")
def health():
    """Simple health endpoint with uptime."""
    uptime_seconds = int(time.time() - START_TIME)
    return {
        "status": "ok",
        "service": "memoire-memory",
        "version": app.version,
        "uptime_seconds": uptime_seconds,
    }


@app.get("/debug/info")
def debug_info() -> dict[str, Any]:
    """
    Small debug endpoint that prints and returns what this service is doing:
    - lists registered routes (paths)
    - returns a few important env vars
    The function prints the same info to the service stdout.
    """
    routes = []
    for r in app.routes:
        # route.path exists on APIRoute and other route types
        path = getattr(r, "path", None) or getattr(r, "prefix", None) or str(r)
        routes.append(path)

    info = {
        "service": "memoire-memory",
        "version": app.version,
        "route_count": len(routes),
        "routes": routes,
        "env": {
            "GRAPH_ENABLED": os.getenv("GRAPH_ENABLED"),
            "DATABASE_URL": os.getenv("DATABASE_URL"),
        },
    }

    # Print to stdout for easy visibility in container logs
    print("DEBUG /debug/info called. Summary:")
    print(info)
    return info


@app.get("/heathinfo")
@app.get("/healthinfo")
def health_info() -> dict[str, Any]:
    """
    Detailed health information for debugging:
    - uptime, pid, platform, python version
    - registered routes and count
    - key environment variables and debug flag
    """
    uptime_seconds = int(time.time() - START_TIME)
    routes = []
    for r in app.routes:
        path = getattr(r, "path", None) or getattr(r, "prefix", None) or str(r)
        routes.append(path)

    info = {
        "service": "memoire-memory",
        "version": app.version,
        "status": "ok",
        "uptime_seconds": uptime_seconds,
        "pid": os.getpid(),
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "route_count": len(routes),
        "routes": routes,
        "env": {
            "GRAPH_ENABLED": os.getenv("GRAPH_ENABLED"),
            "DATABASE_URL": os.getenv("DATABASE_URL"),
        },
        "debug": app.debug,
    }
    print("/healthinfo called. Summary:")
    print(info)
    return info

app.include_router(notes.router)
app.include_router(search.router)
app.include_router(chats.router)
app.include_router(chat_save.router)
app.include_router(documents.router)
app.include_router(profile.router)
app.include_router(inference_rules.router)