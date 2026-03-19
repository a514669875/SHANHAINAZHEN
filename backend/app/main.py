"""FastAPI application entry point."""
import logging
from fastapi import FastAPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, users, templates, projects, procurements, clients, files, ledger, ws
from app.database import run_migrations

run_migrations()

app = FastAPI(
    title="山海纳珍录 - 工程项目采购管理系统",
    description="工程类采购全流程数字化管理",
    version="1.0.0",
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


@app.get("/")
def root():
    return {"message": "山海纳珍录 API", "version": "1.0.0"}


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
