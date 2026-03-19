"""File model for distributed storage."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class File(Base):
    __tablename__ = "t_file"

    id = Column(Integer, primary_key=True, autoincrement=True)
    procurement_id = Column(Integer, ForeignKey("t_procurement.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    file_type = Column(String(50))  # 合同文件/普通文件
    is_contract = Column(Boolean, default=False)
    print_mode = Column(String(10), default="单面")

    # Distributed storage
    owner_user_id = Column(Integer, ForeignKey("t_user.id"), nullable=False)
    storage_computer_ip = Column(String(50))
    storage_computer_name = Column(String(100))
    storage_path = Column(String(500))

    upload_time = Column(DateTime, server_default=func.now())
    upload_by = Column(Integer, ForeignKey("t_user.id"))

    procurement = relationship("Procurement", back_populates="files")
