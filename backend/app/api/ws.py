"""WebSocket 端点 - 全链路实时同步。"""
import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.core.security import decode_token
from app.events_schema import SubscribeMessage
from app.services.realtime_broadcast import (
    register_subscriber,
    unregister_subscriber,
    update_subscriber_context,
)
from app.services.ws_connections import (
    register_connection,
    unregister_connection,
    set_event_loop,
)

logger = logging.getLogger("shanhai")

router = APIRouter(tags=["ws"])


@router.websocket("/api/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token"),
):
    """WebSocket 连接：需携带 token，支持 subscribe 消息更新上下文。"""
    await websocket.accept()

    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return
    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return
    user_id = int(user_id)

    conn_id = str(uuid.uuid4())
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        set_event_loop(loop)
    except RuntimeError:
        pass

    register_connection(conn_id, websocket)
    register_subscriber(conn_id, user_id, context={})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                msg = SubscribeMessage(**data)
                if msg.action == "subscribe" and msg.context:
                    ctx = msg.context.model_dump() if hasattr(msg.context, "model_dump") else (msg.context or {})
                    update_subscriber_context(conn_id, ctx)
                elif msg.action == "unsubscribe":
                    update_subscriber_context(conn_id, {})
            except Exception as e:
                logger.warning("ws parse error: %s", e)
    except WebSocketDisconnect:
        pass
    finally:
        unregister_connection(conn_id)
        unregister_subscriber(conn_id)
        logger.info("ws disconnected conn_id=%s", conn_id)
