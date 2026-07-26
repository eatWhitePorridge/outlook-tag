from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import logging

from app import db
from app.config import get_settings
from app.routers import accounts, auth, mail, settings as settings_router
from app.services import scheduler

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if not settings.secret_key or not settings.admin_password:
        raise RuntimeError("必须设置 SECRET_KEY 与 ADMIN_PASSWORD 环境变量")
    Path(settings.resolve_db_path()).parent.mkdir(parents=True, exist_ok=True)
    db.init_db()
    scheduler.start_scheduler()
    yield
    scheduler.stop_scheduler()


app = FastAPI(title="Mail Workspace", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(mail.router)
app.include_router(settings_router.router)


@app.get("/api/health")
def health():
    return {"ok": True}


# Serve built frontend if present (repo layout: backend/ + frontend/dist)
_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if not _dist.is_dir():
    _dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist.is_dir():
    assets = _dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        target = _dist / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        index = _dist / "index.html"
        if index.is_file():
            return FileResponse(index)
        return {"detail": "frontend not built"}
