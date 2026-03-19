"""Backup script - database and templates."""
import shutil
import sys
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE / "backups"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
TARGET = BACKUP_DIR / f"backup_{TIMESTAMP}"


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    # Backup database
    db_path = BASE / "backend" / "database" / "shanhai.db"
    if db_path.exists():
        shutil.copy2(db_path, TARGET / "shanhai.db")
        print(f"Backed up database to {TARGET / 'shanhai.db'}")
    # Backup templates
    templates = BASE / "backend" / "word_templates"
    if templates.exists():
        shutil.copytree(templates, TARGET / "word_templates", dirs_exist_ok=True)
        print(f"Backed up templates to {TARGET / 'word_templates'}")
    print(f"Backup complete: {TARGET}")


if __name__ == "__main__":
    main()
