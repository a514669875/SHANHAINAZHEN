"""Database connection and session management."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_PATH

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

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


def get_db():
    """Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
