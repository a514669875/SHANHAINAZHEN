"""全链路实时同步 - 事件协议定义。

事件类型与 PRD 8.23、development 2.4 保持一致。
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """系统事件类型。"""
    # 项目
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_UPDATED = "PROJECT_UPDATED"
    PROJECT_DELETED = "PROJECT_DELETED"
    # 采购
    PROCUREMENT_CREATED = "PROCUREMENT_CREATED"
    PROCUREMENT_UPDATED = "PROCUREMENT_UPDATED"
    PROCUREMENT_DELETED = "PROCUREMENT_DELETED"
    # 归档文件
    FILE_UPLOADED = "FILE_UPLOADED"
    FILE_DELETED = "FILE_DELETED"
    # 流程文件
    PROCESS_FILE_CREATED = "PROCESS_FILE_CREATED"
    PROCESS_FILE_UPDATED = "PROCESS_FILE_UPDATED"
    PROCESS_FILE_DELETED = "PROCESS_FILE_DELETED"
    PROCESS_FILE_SYNC_STATUS_CHANGED = "PROCESS_FILE_SYNC_STATUS_CHANGED"
    # 模板
    TEMPLATE_UPDATED = "TEMPLATE_UPDATED"
    # 配置
    CONFIG_CHANGED = "CONFIG_CHANGED"
    # 用户
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_DELETED = "USER_DELETED"
    # 台账
    LEDGER_CREATED = "LEDGER_CREATED"
    LEDGER_UPDATED = "LEDGER_UPDATED"
    # 权限
    PERMISSION_CHANGED = "PERMISSION_CHANGED"


class SubscribeScope(str, Enum):
    """订阅 scope 取值。"""
    PROJECT_LIST = "project_list"
    PROCUREMENT_LIST = "procurement_list"
    PROCUREMENT_DETAIL = "procurement_detail"
    ARCHIVE = "archive"
    ADMIN = "admin"


class RealtimeEvent(BaseModel):
    """标准事件对象。"""
    type: str = Field(..., description="事件类型")
    payload: dict[str, Any] = Field(default_factory=dict, description="事件载荷")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="UTC 时间戳",
    )


class SubscribeContext(BaseModel):
    """订阅上下文。"""
    project_id: Optional[int] = None
    procurement_id: Optional[int] = None
    scope: Optional[str] = None


class SubscribeMessage(BaseModel):
    """订阅消息（前端 → 后端）。"""
    action: str = Field(..., description="subscribe | unsubscribe")
    context: Optional[SubscribeContext] = None
