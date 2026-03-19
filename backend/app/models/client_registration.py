"""Client registration model for distributed file storage."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class ClientRegistration(Base):
    __tablename__ = "t_client_registration"
    __table_args__ = (UniqueConstraint("user_id", "computer_name", name="uq_user_computer"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("t_user.id", ondelete="CASCADE"), nullable=False)
    computer_name = Column(String(100), nullable=False)
    computer_ip = Column(String(50), nullable=False)
    file_service_port = Column(Integer, default=8001)
    file_share_path = Column(String(500), nullable=False)
    status = Column(String(20), default="active")  # active/inactive/offline
    last_heartbeat = Column(DateTime)
    register_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())
