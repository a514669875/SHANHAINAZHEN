"""Initialize database and create default admin user."""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database import engine, Base
from app.models import User, Project, Procurement, Supplier, Ledger, File, ClientRegistration
from app.core.security import get_password_hash


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")


def create_admin():
    """Create default admin user if not exists."""
    from sqlalchemy.orm import Session
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role="系统管理员",
                real_name="系统管理员",
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print("Default admin user created: username=admin, password=admin123")
        else:
            print("Admin user already exists.")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    create_admin()
