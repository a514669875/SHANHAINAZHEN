"""User schemas."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    username: str
    role: str = "采购管理员"
    real_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    computer_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    role: Optional[str] = None
    real_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    computer_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(
        default=None,
        description="新密码；不传或空字符串表示不修改",
    )


class UserResponse(UserBase):
    id: int
    is_active: bool
    create_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[int] = None


class LoginRequest(BaseModel):
    username: str
    password: str
