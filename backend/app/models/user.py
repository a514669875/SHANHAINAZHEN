"""User model."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "t_user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="采购管理员")  # 采购管理员/系统管理员
    real_name = Column(String(50))
    phone = Column(String(20))
    email = Column(String(100))

    # Computer info for distributed file storage
    computer_name = Column(String(100))
    computer_ip = Column(String(50), index=True)
    file_service_port = Column(Integer, default=8001)
    file_share_path = Column(String(500))
    is_online = Column(Boolean, default=False)
    last_heartbeat = Column(DateTime)

    is_active = Column(Boolean, default=True)
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())
