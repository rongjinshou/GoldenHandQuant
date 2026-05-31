import asyncio
import json
import logging
from datetime import datetime

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """WebSocket 连接管理器。

    负责连接生命周期管理、消息广播和心跳检测。
    """

    def __init__(self, heartbeat_interval: float = 30.0) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_task: asyncio.Task | None = None

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        """接受并注册 WebSocket 连接。"""
        await websocket.accept()
        self._connections[client_id] = websocket
        logger.info("WebSocket connected: %s (total=%d)", client_id, self.connection_count)

    def disconnect(self, client_id: str) -> None:
        """移除 WebSocket 连接。"""
        if client_id in self._connections:
            del self._connections[client_id]
            logger.info("WebSocket disconnected: %s (total=%d)", client_id, self.connection_count)

    async def send_personal(self, client_id: str, data: dict) -> None:
        """向单个客户端发送消息。"""
        ws = self._connections.get(client_id)
        if ws is None:
            return
        try:
            await ws.send_json(data)
        except Exception:
            logger.debug("Failed to send to %s, removing", client_id)
            self.disconnect(client_id)

    async def broadcast(self, data: dict) -> None:
        """向所有已连接客户端广播消息。"""
        if not self._connections:
            return

        message = json.dumps(data, default=_json_serializer)
        disconnected: list[str] = []

        for client_id, ws in self._connections.items():
            try:
                await ws.send_text(message)
            except Exception:
                logger.debug("Broadcast failed for %s", client_id)
                disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)

    async def start_heartbeat(self) -> None:
        """启动心跳检测协程。"""
        if self._heartbeat_task is not None:
            return
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_heartbeat(self) -> None:
        """停止心跳检测协程。"""
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

    async def _heartbeat_loop(self) -> None:
        """定时发送心跳，检测断开的连接。"""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            heartbeat = {
                "type": "heartbeat",
                "timestamp": datetime.now().isoformat(),
                "connections": self.connection_count,
            }
            await self.broadcast(heartbeat)

    async def close_all(self) -> None:
        """关闭所有连接。"""
        await self.stop_heartbeat()
        for client_id in list(self._connections):
            ws = self._connections[client_id]
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()


def _json_serializer(obj: object) -> str:
    """JSON 序列化辅助，处理 datetime 等类型。"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
