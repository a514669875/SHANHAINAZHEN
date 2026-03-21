"""
Pytest 启动前设置独立 SQLite 与文件目录，避免污染开发库。

必须在首次 import app 之前设置环境变量。
"""
from __future__ import annotations

import os
import tempfile

# --- 独立测试库与流程/归档目录（仅本 conftest 被 pytest 加载时生效）---
_fd, _TEST_DB = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["SHANHAI_DATABASE_PATH"] = _TEST_DB
os.environ["PROCUREMENT_PROCESS_ROOT"] = tempfile.mkdtemp(prefix="shanhai_tproc_")
os.environ["ARCHIVED_FILE_ROOT"] = tempfile.mkdtemp(prefix="shanhai_tarch_")

import app.models  # noqa: E402 — 注册 ORM 元数据
from app.database import Base, engine, SessionLocal  # noqa: E402

Base.metadata.create_all(bind=engine)

from app.main import app  # noqa: E402 — 会执行 run_migrations（表已存在）

from app.models.user import User  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402

_sess = SessionLocal()
try:
    if not _sess.query(User).filter(User.username == "admin").first():
        _sess.add(
            User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role="系统管理员",
                real_name="系统管理员",
                is_active=True,
            )
        )
        _sess.commit()
finally:
    _sess.close()

import pytest
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
