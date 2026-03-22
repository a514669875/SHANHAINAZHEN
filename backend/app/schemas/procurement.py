"""Procurement schemas."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import date


class SupplierInput(BaseModel):
    supplier_name: str
    contact_person: str
    contact_phone: str
    business_scope: str
    tax_rate: str
    quoted_price: float


class TimeRecordInput(BaseModel):
    flow_name: str
    date_val: str


class ProcurementStep1(BaseModel):
    procurement_type: str  # 材料采购/材料租赁/设备采购/机械租赁
    procurement_method: str  # 邀请询比/单一来源/直接采购/补充协议/五选二


class ProcurementStep2(BaseModel):
    # 继承step1
    procurement_type: str
    procurement_method: str
    # 类别
    leibie: str = "材料物资类"
    # 项目基础信息 (from project)
    project_name: str
    project_number: str
    project_id: str
    construction_unit: str
    total_contract_price: float
    project_address: str
    department: str
    site_manager: str
    site_manager_phone: str
    # 采购信息
    procurement_project_name: str
    content: str
    control_price: float
    tax_method: str = "一般计税方法计算"
    contract_format: str = "采用非公司印发的合同标准文本编制"
    use_standard_contract: str = "是"
    passed_procurement: str = "是"
    reviewed: str = "是"
    # 日期字段 (年/月/日 三个文本输入框)
    sign_date: str = ""
    gonggao_year: str = ""
    gonggao_month: str = ""
    gonggao_day: str = ""
    yixiang_baoming_jiezhi_year: str = ""
    yixiang_baoming_jiezhi_month: str = ""
    yixiang_baoming_jiezhi_day: str = ""
    jiaoyi_fengmian_year: str = ""
    jiaoyi_fengmian_month: str = ""
    jiaoyi_wenjian_year: str = ""
    jiaoyi_wenjian_month: str = ""
    jiaoyi_wenjian_day: str = ""
    jiaoyi_wenjian_huoqv_jiezhi_year: str = ""
    jiaoyi_wenjian_huoqv_jiezhi_month: str = ""
    jiaoyi_wenjian_huoqv_jiezhi_day: str = ""
    xiangying_dijiao_jiezhi_year: str = ""
    xiangying_dijiao_jiezhi_month: str = ""
    xiangying_dijiao_jiezhi_day: str = ""
    qianding_year: str = ""
    qianding_month: str = ""
    qianding_day: str = ""
    # 五选二
    biaoduanming1: str = ""
    biaoduanming2: str = ""
    kongzhijia_biao1: Optional[float] = None
    kongzhijia_biao2: Optional[float] = None
    chengjiao_jine1: Optional[float] = None  # 成交金额1，用户输入
    chengjiao_jine2: Optional[float] = None  # 成交金额2，用户输入
    # 流程时间末行「合同交底」文本，同步入 form_data（与 _time_records 分列存储）
    hetong_jiaodi: str = ""
    # 补充协议：用户填写的「控制价」须进 form_data，供清单/台账/总览读取（与根级 supplement_control_price 同步）
    supplement_control_price: Optional[float] = None


class ProcurementCreate(BaseModel):
    project_id: int
    step1: ProcurementStep1
    step2: ProcurementStep2
    suppliers: List[SupplierInput]
    time_records: List[dict]  # [{flow_name, date_val}, ...]
    parent_contract_id: Optional[int] = None  # 补充协议时
    supplement_amount: Optional[float] = None  # 补充协议 新增金额
    supplement_content: Optional[str] = None  # 补充协议 补充内容
    supplement_control_price: Optional[float] = None  # 补充协议 控制价（用户输入）
    section_a_name: Optional[str] = None  # 五选二 一标段名称
    section_b_name: Optional[str] = None  # 五选二 二标段名称
    is_draft: Optional[bool] = False  # 暂存草稿


class ProcurementRemarkPatch(BaseModel):
    """采购清单「备注」列单独保存，写入 form_data.remark。"""

    remark: str = ""


class ProcurementUpdate(BaseModel):
    """Partial update for procurement - triggers folder rename when content/project_name changes."""
    project_name: Optional[str] = None
    content: Optional[str] = None
    form_data: Optional[str] = None  # 完整表单JSON，用于暂存后完成
    control_price: Optional[float] = None  # 控制价（非补充协议时从 form_data 同步）
    suppliers: Optional[List[SupplierInput]] = None  # 暂存时更新供应商列表
    supplement_amount: Optional[float] = None  # 补充协议暂存时
    supplement_content: Optional[str] = None  # 补充协议暂存时
