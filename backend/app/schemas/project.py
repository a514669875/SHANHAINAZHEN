"""Project schemas."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import date


class ProjectBase(BaseModel):
    funding_type: str  # 工程类/自有资金
    project_type: str  # 集团内项目/集团外项目
    project_number: str
    project_id: str  # 工程编号
    project_name: str
    department: str
    site_manager: str
    site_manager_phone: str
    construction_unit: str
    construction_contact_person: Optional[str] = ""
    construction_contact_phone: Optional[str] = ""
    total_contract_price: float
    project_duration: Optional[str] = None  # 工程工期
    funding_source: str
    project_address: str
    procurement_officers: Optional[str] = ""  # comma-separated user IDs, may be None in DB


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    funding_type: Optional[str] = None
    project_type: Optional[str] = None
    project_number: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    department: Optional[str] = None
    site_manager: Optional[str] = None
    site_manager_phone: Optional[str] = None
    construction_unit: Optional[str] = None
    construction_contact_person: Optional[str] = None
    construction_contact_phone: Optional[str] = None
    total_contract_price: Optional[float] = None
    project_duration: Optional[str] = None
    funding_source: Optional[str] = None
    project_address: Optional[str] = None
    procurement_officers: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: int
    create_date: Optional[date] = None
    # 服务端解析 procurement_officers ID 列表为人名（多行）；清单/详情统一返回，供采购管理员等无法拉全量用户列表时展示
    procurement_officer_display: str = ""

    class Config:
        from_attributes = True
