"""发射实时事件 - 供各模块 CRUD 成功后调用。"""
from app.events_schema import EventType, RealtimeEvent
from app.services.realtime_broadcast import emit_event


def emit(
    event_type: str | EventType,
    payload: dict | None = None,
) -> None:
    """发射事件到订阅者。"""
    ev = RealtimeEvent(type=str(event_type), payload=payload or {})
    emit_event(ev)
