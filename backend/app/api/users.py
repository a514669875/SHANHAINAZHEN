"""User management API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.core.auth import get_current_user, get_current_admin
from app.core.security import get_password_hash
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.services.emit_event import emit
from app.events_schema import EventType

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出用户：系统管理员可见全部；采购管理员仅可见本人（用于工程「经办人」等下拉，且前端限制仅选自己）。"""
    if current_user.role == "系统管理员":
        return db.query(User).all()
    return [current_user]


@router.post("", response_model=UserResponse)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Create user (admin only)."""
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        role=data.role,
        real_name=data.real_name,
        phone=data.phone,
        email=data.email,
        computer_name=data.computer_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    emit(EventType.USER_CREATED, {"user_id": user.id})
    return user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Get user by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Update user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    payload = data.model_dump(exclude_unset=True)
    new_password = payload.pop("password", None)
    for k, v in payload.items():
        setattr(user, k, v)
    if new_password is not None and str(new_password).strip():
        user.password_hash = get_password_hash(new_password.strip())
    db.commit()
    db.refresh(user)
    emit(EventType.USER_UPDATED, {"user_id": user.id})
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Delete user (admin only)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete self")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    emit(EventType.USER_DELETED, {"user_id": user_id})
    return {"message": "ok"}
