"""Authentication dependencies."""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.core.security import decode_token
from app.config import SINGLE_USER_MODE
from app.core.security import get_password_hash

security = HTTPBearer(auto_error=False)


def _get_or_create_single_user(db: Session) -> User:
    user = db.query(User).filter(User.is_active == True).order_by(User.id.asc()).first()  # noqa: E712
    if user:
        return user
    user = User(
        username="admin",
        password_hash=get_password_hash("admin123"),
        role="系统管理员",
        real_name="系统管理员",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if SINGLE_USER_MODE:
        return _get_or_create_single_user(db)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """用于 GET /auth/me：未登录或 token 无效时返回 None（HTTP 200 + null），避免无意义 401 日志与前端全局拦截误跳转。"""
    if SINGLE_USER_MODE:
        return _get_or_create_single_user(db)
    if not credentials:
        return None
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    user = db.query(User).filter(User.id == uid).first()
    if not user or not user.is_active:
        return None
    return user


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if SINGLE_USER_MODE:
        return current_user
    if current_user.role != "系统管理员":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def get_authenticated_user(current_user: User = Depends(get_current_user)) -> User:
    """
    任意已登录且启用的用户（不区分系统管理员 / 采购管理员）。
    用于台账/工程等 **导出 Excel** 等只读导出接口，与业务上的「谁能看见列表」一致，不在此处再做角色限制。
    """
    return current_user
