#!/usr/bin/env python3
"""
清空并重建 SQLite 数据库（所有业务数据删除，仅保留默认管理员）。

用法（项目根目录）:
  backend\\venv\\Scripts\\python.exe scripts\\reset_database.py

环境变量 SHANHAI_DATABASE_PATH 与后端一致。请先停止正在运行的 uvicorn，避免 Windows 下文件被占用。
"""
from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.config import DATABASE_PATH  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from app.models import (  # noqa: F401, E402 — 注册全部表到 metadata
    ClientRegistration,
    File,
    Ledger,
    ProcessFileSyncStatus,
    Procurement,
    Project,
    Supplier,
    User,
)


def _remove_sqlite_files(db_path: Path) -> None:
    engine.dispose()
    candidates = [db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")]
    for p in candidates:
        try:
            if p.exists():
                p.unlink()
                print(f"已删除: {p}")
        except OSError as e:
            print(f"警告: 无法删除 {p}: {e}")
            raise SystemExit(1) from e


def main() -> int:
    db_path = Path(DATABASE_PATH)
    print("=" * 50)
    print("数据库重置（不可恢复）")
    print(f"目标文件: {db_path.resolve()}")
    print("=" * 50)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _remove_sqlite_files(db_path)
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    try:
        admin = User(
            username="admin",
            password_hash=get_password_hash("admin123"),
            role="系统管理员",
            real_name="系统管理员",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print("已创建默认管理员: admin / admin123")
    finally:
        db.close()
    print("完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
