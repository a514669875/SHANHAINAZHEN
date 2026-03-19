"""Project (工程项目) model."""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Project(Base):
    __tablename__ = "t_project"

    id = Column(Integer, primary_key=True, autoincrement=True)
    funding_type = Column(String(50))  # 工程类/自有资金
    project_type = Column(String(50))  # 集团内项目/集团外项目
    project_number = Column(String(100))  # 项目编号
    project_id = Column(String(100))  # 工程编号
    project_name = Column(String(255))  # 工程名称
    department = Column(String(100))  # 项目实施部门
    site_manager = Column(String(100))  # 项目现场管理员
    site_manager_phone = Column(String(50))  # 项目现场管理员联系方式
    construction_unit = Column(String(255))  # 建设单位
    total_contract_price = Column(Float)  # 总包合同价
    project_duration = Column(String(500))  # 工程工期
    funding_source = Column(String(100))  # 资金来源
    project_address = Column(String(500))  # 项目地址
    procurement_officers = Column(String(500))  # 经办人ID列表，JSON或逗号分隔
    create_date = Column(Date)
    create_time = Column(DateTime, server_default=func.now())

    # Relationships - cascade delete so project delete removes procurements/ledgers
    procurements = relationship("Procurement", back_populates="project", cascade="all, delete-orphan")
    ledgers = relationship("Ledger", back_populates="project", cascade="all, delete-orphan")
