"""Process file sync status - 流程文件同步状态。"""
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class ProcessFileSyncStatus(Base):
    __tablename__ = "t_process_file_sync_status"
    __table_args__ = (UniqueConstraint("procurement_id", "filename", name="uq_procurement_filename"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    procurement_id = Column(Integer, ForeignKey("t_procurement.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    sync_status = Column(String(50), nullable=False, default="SYNCED")  # SYNCED | USER_MODIFIED | OUTDATED_MANUAL_MERGE_REQUIRED
    file_mtime_at_sync = Column(Float, nullable=True)  # 上次同步时文件 mtime，用于自动检测用户是否手动修改
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
