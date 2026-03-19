"""Procurement (采购项目) model."""
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Procurement(Base):
    __tablename__ = "t_procurement"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("t_project.id", ondelete="CASCADE"), nullable=False)
    procurement_type = Column(String(50))  # 材料采购/设备采购/机械租赁
    procurement_method = Column(String(50))  # 邀请询比/单一来源/直接采购/补充协议/五选二
    project_name = Column(String(255))  # 采购项目名称
    content = Column(String(500))  # 采购内容
    control_price = Column(Float)  # 控制价
    budget = Column(Float)  # 采购预算
    tax_method = Column(String(100))  # 计税方式
    contract_format = Column(String(255))  # 合同文本格式
    use_standard_contract = Column(Boolean, default=True)
    passed_procurement = Column(Boolean, default=True)
    reviewed = Column(Boolean, default=True)
    create_date = Column(Date)
    contract_number = Column(String(100))  # 合同编号
    is_draft = Column(Boolean, default=False)  # 暂存草稿
    is_dual_contract = Column(Boolean, default=False)  # 五选二模式
    parent_contract_id = Column(Integer, ForeignKey("t_procurement.id"))  # 补充协议关联主合同
    contract_section = Column(String(50))  # 一标段/二标段 (五选二)
    sign_date = Column(String(50))  # 签订日期
    # Additional form fields (JSON or separate columns for key ones)
    form_data = Column(Text)  # JSON string for extra form fields
    create_time = Column(DateTime, server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="procurements")
    suppliers = relationship("Supplier", back_populates="procurement", cascade="all, delete-orphan")
    ledgers = relationship("Ledger", back_populates="procurement", cascade="all, delete-orphan")
    files = relationship("File", back_populates="procurement", cascade="all, delete-orphan")
    parent_contract = relationship("Procurement", remote_side=[id])
