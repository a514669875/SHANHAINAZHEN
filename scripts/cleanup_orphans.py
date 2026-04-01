#!/usr/bin/env python3
"""
清理数据库中的孤儿行：采购或工程项目已从库中删除，但 t_ledger / t_file / t_supplier 等仍残留。

用法（在项目根目录）:
  backend\\venv\\Scripts\\python.exe scripts\\cleanup_orphans.py

或使用当前环境已安装依赖的 python，需能 import app（已将 backend 加入 sys.path）。

环境变量 SHANHAI_DATABASE_PATH 可指向其他 SQLite 文件（与后端一致）。
"""
from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database import engine  # noqa: E402
from app.services.orphan_cleanup import run_orphan_cleanup  # noqa: E402
from app.config import DATABASE_PATH  # noqa: E402


def main() -> int:
    print(f"数据库: {DATABASE_PATH}")
    counts = run_orphan_cleanup(engine)
    total = 0
    for label, n in counts.items():
        print(f"  {label}: {n}")
        total += n
    print(f"合计删除行数: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
