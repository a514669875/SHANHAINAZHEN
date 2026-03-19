"""WebSocket 连接存储，供 ws 与 broadcast 共用。"""
import asyncio
from typing import Any, Optional

_connections: dict[str, Any] = {}  # conn_id -> WebSocket
_loop: Optional[asyncio.AbstractEventLoop] = None


def register_connection(conn_id: str, ws: Any) -> None:
    _connections[conn_id] = ws


def unregister_connection(conn_id: str) -> None:
    _connections.pop(conn_id, None)


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


async def _send_to_connection(conn_id: str, payload: str) -> None:
    ws = _connections.get(conn_id)
    if ws:
        await ws.send_text(payload)


def connection_send(conn_id: str, payload: str) -> None:
    """向指定连接发送消息（从 sync 上下文调用）。"""
    if _loop is None:
        return
    asyncio.run_coroutine_threadsafe(_send_to_connection(conn_id, payload), _loop)
