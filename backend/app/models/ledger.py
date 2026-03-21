"""Ledger (台账) model."""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Ledger(Base):
    __tablename__ = "t_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("t_project.id", ondelete="CASCADE"), nullable=False)
    procurement_id = Column(Integer, ForeignKey("t_procurement.id", ondelete="CASCADE"), nullable=False)
    group_type = Column(String(50))  # 集团内/外项目
    procurement_method = Column(String(50))
    department = Column(String(100))
    project_number = Column(String(100))
    contract_number = Column(String(100))
    project_name = Column(String(255))
    procurement_name = Column(String(255))
    supplier = Column(String(255))
    supplier_contact_person = Column(String(100))  # 中标供应商联系人（与采购同步）
    supplier_contact_phone = Column(String(100))  # 中标供应商联系方式（与采购同步）
    contract_price = Column(Float)
    sign_date = Column(String(50))
    content = Column(String(500))
    other_participants = Column(Text)  # 其余参与方，换行分隔
    control_price = Column(Float)
    funding_source = Column(String(100))
    officer = Column(String(255))  # 经办人，可多选
    funding_type = Column(String(50))
    file_path = Column(String(500))
    pdf_preview_path = Column(String(500))
    parent_contract_number = Column(String(100))  # 所属主合同
    supplement_contracts = Column(Text)  # 补充协议编号，换行分隔
    create_time = Column(DateTime, server_default=func.now())  # 录入时间，台账生成时间

    project = relationship("Project", back_populates="ledgers")
    procurement = relationship("Procurement", back_populates="ledgers")
