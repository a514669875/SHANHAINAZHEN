"""FastAPI application entry point."""
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, users, templates, projects, procurements, clients, files, ledger, ws
from app.config import REPO_ROOT, get_static_dist_dir
from app.database import run_migrations

run_migrations()


def _read_app_version() -> str:
    try:
        vf = REPO_ROOT / "VERSION.txt"
        if vf.is_file():
            line = vf.read_text(encoding="utf-8").strip().splitlines()[0]
            return (line or "1.0.0")[:64]
    except Exception:
        pass
    return "1.0.0"


_APP_VERSION = _read_app_version()

app = FastAPI(
    title="山海纳珍录 - 工程项目采购管理系统",
    description="工程类采购全流程数字化管理",
    version=_APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(templates.router)
app.include_router(projects.router)
app.include_router(procurements.router)
app.include_router(clients.router)
app.include_router(files.router)
app.include_router(ledger.router)
app.include_router(ws.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/stats")
def stats():
    """Simple stats for home page (no auth for dashboard)."""
    from app.database import SessionLocal
    from app.models.project import Project
    from app.models.procurement import Procurement
    from app.models.ledger import Ledger

    db = SessionLocal()
    try:
        return {
            "projects": db.query(Project).count(),
            "procurements": db.query(Procurement).count(),
            "ledgers": db.query(Ledger).count(),
        }
    finally:
        db.close()


STATIC_DIST = get_static_dist_dir()

if not STATIC_DIST:

    @app.get("/")
    def root():
        return {"message": "山海纳珍录 API", "version": _APP_VERSION}

else:
    _log = logging.getLogger("shanhai")
    _log.info("Serving SPA static files from %s", STATIC_DIST)

    _assets = STATIC_DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="spa_assets")

    def _safe_dist_file(rel: str) -> Path | None:
        rel = rel.replace("\\", "/").lstrip("/")
        if not rel:
            return None
        parts = rel.split("/")
        if ".." in parts or any(p.startswith("..") for p in parts):
            return None
        candidate = (STATIC_DIST / rel).resolve()
        try:
            candidate.relative_to(STATIC_DIST.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    @app.get("/", include_in_schema=False)
    async def spa_index():
        return FileResponse(STATIC_DIST / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # API / WebSocket 已由上方路由处理；若落入此处说明未匹配，返回 404
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        f = _safe_dist_file(full_path)
        if f:
            return FileResponse(f)
        return FileResponse(STATIC_DIST / "index.html")
