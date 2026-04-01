"""清理引用已不存在采购/工程的孤儿行（历史外键未级联或旧逻辑残留）。"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def run_orphan_cleanup(engine: Engine) -> dict[str, int]:
    """
    逐条执行 DELETE（各语句独立事务），避免某表不存在时整批失败。
    返回各语句删除行数（SQLite 下通常为实际删除数）。
    """
    statements: list[tuple[str, str]] = [
        (
            "t_ledger (procurement 已不存在)",
            "DELETE FROM t_ledger WHERE procurement_id NOT IN (SELECT id FROM t_procurement)",
        ),
        (
            "t_ledger (project 已不存在)",
            "DELETE FROM t_ledger WHERE project_id NOT IN (SELECT id FROM t_project)",
        ),
        (
            "t_file (procurement 已不存在)",
            "DELETE FROM t_file WHERE procurement_id NOT IN (SELECT id FROM t_procurement)",
        ),
        (
            "t_supplier (procurement 已不存在)",
            "DELETE FROM t_supplier WHERE procurement_id NOT IN (SELECT id FROM t_procurement)",
        ),
        (
            "t_process_file_sync_status (procurement 已不存在)",
            "DELETE FROM t_process_file_sync_status WHERE procurement_id NOT IN (SELECT id FROM t_procurement)",
        ),
    ]
    counts: dict[str, int] = {}
    for label, sql in statements:
        try:
            with engine.begin() as conn:
                r = conn.execute(text(sql))
                rc = r.rowcount
                counts[label] = int(rc) if rc is not None and rc >= 0 else 0
        except Exception:
            counts[label] = 0
    return counts
