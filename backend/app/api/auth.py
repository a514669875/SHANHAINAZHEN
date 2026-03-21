"""Authentication API."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token
from app.core.auth import get_current_user_optional
from app.schemas.user import LoginRequest, Token, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")
    return Token(
        access_token=create_access_token(data={"sub": str(user.id)}),
        token_type="bearer",
    )


@router.get("/me", response_model=Optional[UserResponse])
def get_me(current_user: Optional[User] = Depends(get_current_user_optional)):
    """未携带 token 或 token 无效时返回 200 + null，由前端清理本地会话。"""
    return current_user
