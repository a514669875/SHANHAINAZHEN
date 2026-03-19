"""Migration: add project_duration to t_project, create_time to t_ledger."""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database import engine
from sqlalchemy import text


def migrate():
    with engine.begin() as conn:
        for col, table, col_type in [
            ("project_duration", "t_project", "VARCHAR(500)"),
            ("create_time", "t_ledger", "DATETIME"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                print(f"Added {col} to {table}")
            except Exception as e:
                err = str(e).lower()
                if "duplicate column" in err or "already exists" in err:
                    print(f"{col} already exists in {table}")
                else:
                    raise
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
