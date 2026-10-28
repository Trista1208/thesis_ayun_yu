from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.deps import load_env
from api.routes import assessments, auth, chat, experts, extract, health, knowledge, memory, reviews, tickets, voice

load_env()

app = FastAPI(
    title="Joule for AYUN · Sport Plan API",
    description="FastAPI layer for the Joule sport-prescription engine at AYUN Longevity Clinic",
    version="1.0.0",
)

_origins = os.environ.get("CORS_ORIGIN", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(assessments.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(experts.router, prefix="/api")
app.include_router(extract.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(voice.router, prefix="/api")

_WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"


def _spa_enabled() -> bool:
    return _WEB_DIST.is_dir() and (_WEB_DIST / "index.html").is_file()


@app.get("/")
def root():
    if _spa_enabled():
        return FileResponse(_WEB_DIST / "index.html")
    return {"service": "ayun-api", "docs": "/docs"}


def _mount_spa() -> None:
    if not _spa_enabled():
        return
    assets = _WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="spa-assets")

    @app.get("/{spa_path:path}", include_in_schema=False)
    def spa_fallback(spa_path: str):
        if spa_path.startswith("api/") or spa_path in ("docs", "openapi.json") or spa_path.startswith("docs/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = _WEB_DIST / spa_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_WEB_DIST / "index.html")


_mount_spa()
