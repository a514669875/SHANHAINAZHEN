"""Database connection and session management."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import event
from app.config import DATABASE_PATH

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite 默认关闭外键约束；显式开启以保证 ON DELETE CASCADE 生效。"""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def run_migrations():
    """Add columns if missing."""
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE t_procurement ADD COLUMN is_draft BOOLEAN DEFAULT 0"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE t_procurement ADD COLUMN is_dual_contract BOOLEAN DEFAULT 0"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE t_procurement ADD COLUMN contract_section VARCHAR(50)"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE t_supplier ADD COLUMN contract_section VARCHAR(50)"))
            conn.commit()
    except Exception:
        pass
    # 流程文件同步状态表
    try:
        from app.models.process_file_sync_status import ProcessFileSyncStatus
        ProcessFileSyncStatus.__table__.create(engine, checkfirst=True)
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE t_process_file_sync_status ADD COLUMN file_mtime_at_sync REAL"))
            conn.commit()
    except Exception:
        pass
    # 清理历史孤儿状态（旧版本未开启外键级联时遗留）
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "DELETE FROM t_process_file_sync_status "
                "WHERE procurement_id NOT IN (SELECT id FROM t_procurement)"
            ))
            conn.commit()
    except Exception:
        pass
    for stmt in [
        "ALTER TABLE t_project ADD COLUMN construction_contact_person VARCHAR(100)",
        "ALTER TABLE t_project ADD COLUMN construction_contact_phone VARCHAR(100)",
        "ALTER TABLE t_ledger ADD COLUMN supplier_contact_person VARCHAR(100)",
        "ALTER TABLE t_ledger ADD COLUMN supplier_contact_phone VARCHAR(100)",
        "ALTER TABLE t_ledger ADD COLUMN other_participants TEXT",
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(text(stmt))
                conn.commit()
        except Exception:
            pass


def get_db():
    """Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
