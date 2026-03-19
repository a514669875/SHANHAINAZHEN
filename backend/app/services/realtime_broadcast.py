"""全链路实时同步 - 广播层。

单实例内存广播；预留 Redis Pub/Sub 接口便于多实例扩展。
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.events_schema import EventType, RealtimeEvent

logger = logging.getLogger("shanhai.realtime")


@dataclass
class SubscriberContext:
    """单个连接的订阅上下文。"""
    project_id: Optional[int] = None
    procurement_id: Optional[int] = None
    scope: Optional[str] = None


@dataclass
class Subscriber:
    """WebSocket 订阅者。"""
    conn_id: str
    user_id: int
    context: SubscriberContext = field(default_factory=SubscriberContext)


# 内存存储：conn_id -> Subscriber
_subscribers: dict[str, Subscriber] = {}


def _get_ws_send():
    from app.services.ws_connections import connection_send
    return connection_send


def _event_matches_subscriber(event: RealtimeEvent, sub: Subscriber) -> bool:
    """判断事件是否应推送给该订阅者。"""
    payload = event.payload or {}
    pj = payload.get("project_id")
    pc = payload.get("procurement_id")
    evt = event.type

    # 全局事件（管理员 scope）
    if sub.context.scope == "admin":
        if evt in (
            EventType.TEMPLATE_UPDATED,
            EventType.CONFIG_CHANGED,
            EventType.USER_CREATED,
            EventType.USER_UPDATED,
            EventType.USER_DELETED,
            EventType.PERMISSION_CHANGED,
        ):
            return True

    # 项目级
    if evt in (EventType.PROJECT_CREATED, EventType.PROJECT_UPDATED, EventType.PROJECT_DELETED):
        if sub.context.project_id is not None and pj is not None:
            return sub.context.project_id == pj
        if sub.context.scope == "project_list":
            return True

    # 采购级
    if evt in (
        EventType.PROCUREMENT_CREATED,
        EventType.PROCUREMENT_UPDATED,
        EventType.PROCUREMENT_DELETED,
        EventType.FILE_UPLOADED,
        EventType.FILE_DELETED,
        EventType.PROCESS_FILE_CREATED,
        EventType.PROCESS_FILE_UPDATED,
        EventType.PROCESS_FILE_DELETED,
        EventType.PROCESS_FILE_SYNC_STATUS_CHANGED,
        EventType.LEDGER_CREATED,
        EventType.LEDGER_UPDATED,
    ):
        if sub.context.project_id is not None and pj is not None and sub.context.project_id != pj:
            return False
        if sub.context.procurement_id is not None and pc is not None:
            return sub.context.procurement_id == pc
        if sub.context.procurement_id is None and sub.context.project_id == pj:
            return True
        if sub.context.scope in ("procurement_list", "procurement_detail", "archive"):
            return sub.context.project_id == pj if pj else True

    return False


def register_subscriber(conn_id: str, user_id: int, context: Optional[dict] = None) -> None:
    """注册订阅者。"""
    ctx = SubscriberContext()
    if context:
        ctx.project_id = context.get("project_id")
        ctx.procurement_id = context.get("procurement_id")
        ctx.scope = context.get("scope")
    _subscribers[conn_id] = Subscriber(conn_id=conn_id, user_id=user_id, context=ctx)
    logger.info("realtime: subscriber registered conn_id=%s user_id=%s ctx=%s", conn_id, user_id, context)


def unregister_subscriber(conn_id: str) -> None:
    """移除订阅者。"""
    _subscribers.pop(conn_id, None)
    logger.info("realtime: subscriber unregistered conn_id=%s", conn_id)


def update_subscriber_context(conn_id: str, context: dict) -> None:
    """更新订阅上下文。"""
    sub = _subscribers.get(conn_id)
    if sub:
        sub.context.project_id = context.get("project_id")
        sub.context.procurement_id = context.get("procurement_id")
        sub.context.scope = context.get("scope")


def emit_event(event: RealtimeEvent) -> None:
    """发射事件，按订阅精准推送给匹配的前端连接。"""
    send_fn = _get_ws_send()
    if not send_fn:
        logger.warning("realtime: ws send not available, event dropped: %s", event.type)
        return
    payload_str = json.dumps(event.model_dump(), ensure_ascii=False)
    sent = 0
    for sub in list(_subscribers.values()):
        if _event_matches_subscriber(event, sub):
            try:
                send_fn(sub.conn_id, payload_str)
                sent += 1
            except Exception as e:
                logger.warning("realtime: send failed conn_id=%s: %s", sub.conn_id, e)
    if sent:
        logger.debug("realtime: event %s sent to %d subscribers", event.type, sent)
