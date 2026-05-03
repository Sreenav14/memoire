from fastapi import FastAPI
from dotenv import load_dotenv
import os
from typing import Any

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

app.include_router(notes.router)
app.include_router(search.router)
app.include_router(chats.router)
app.include_router(chat_save.router)
app.include_router(documents.router)
app.include_router(profile.router)
app.include_router(inference_rules.router)