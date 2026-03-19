"""Officer (经办人) utilities - resolve user IDs to names."""
from sqlalchemy.orm import Session
from app.models.user import User


def resolve_officer_names(db: Session, officer_ids: str) -> str:
    """Resolve comma-separated user IDs to names, newline-separated."""
    if not officer_ids:
        return ""
    ids = [x.strip() for x in officer_ids.split(",") if x.strip()]
    if not ids:
        return ""
    users = db.query(User).filter(User.id.in_([int(i) for i in ids if i.isdigit()])).all()
    id_to_name = {str(u.id): (u.real_name or u.username or str(u.id)) for u in users}
    return "\n".join(id_to_name.get(i, i) for i in ids)
