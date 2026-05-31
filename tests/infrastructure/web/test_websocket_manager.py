import asyncio

import anyio
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.web.websocket_manager import WebSocketManager


class TestWebSocketManager:
    def test_initial_connection_count(self):
        mgr = WebSocketManager()
        assert mgr.connection_count == 0

    @pytest.mark.anyio
    async def test_connect_adds_connection(self):
        mgr = WebSocketManager()
        ws = AsyncMock()
        await mgr.connect("client-1", ws)
        assert mgr.connection_count == 1
        ws.accept.assert_awaited_once()

    @pytest.mark.anyio
    async def test_disconnect_removes_connection(self):
        mgr = WebSocketManager()
        ws = AsyncMock()
        await mgr.connect("client-1", ws)
        mgr.disconnect("client-1")
        assert mgr.connection_count == 0

    @pytest.mark.anyio
    async def test_disconnect_nonexistent_is_noop(self):
        mgr = WebSocketManager()
        mgr.disconnect("nonexistent")
        assert mgr.connection_count == 0

    @pytest.mark.anyio
    async def test_send_personal(self):
        mgr = WebSocketManager()
        ws = AsyncMock()
        await mgr.connect("client-1", ws)
        await mgr.send_personal("client-1", {"type": "test"})
        ws.send_json.assert_awaited_once_with({"type": "test"})

    @pytest.mark.anyio
    async def test_send_personal_to_disconnected_is_noop(self):
        mgr = WebSocketManager()
        await mgr.send_personal("nonexistent", {"type": "test"})

    @pytest.mark.anyio
    async def test_broadcast_to_multiple(self):
        mgr = WebSocketManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await mgr.connect("c1", ws1)
        await mgr.connect("c2", ws2)
        await mgr.broadcast({"type": "update", "data": 42})
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()

    @pytest.mark.anyio
    async def test_broadcast_empty_is_noop(self):
        mgr = WebSocketManager()
        await mgr.broadcast({"type": "test"})

    @pytest.mark.anyio
    async def test_broadcast_removes_failed_connections(self):
        mgr = WebSocketManager()
        ws_good = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_text.side_effect = Exception("connection lost")
        await mgr.connect("good", ws_good)
        await mgr.connect("bad", ws_bad)
        await mgr.broadcast({"type": "test"})
        assert mgr.connection_count == 1
        assert "good" in mgr._connections

    @pytest.mark.anyio
    async def test_heartbeat_lifecycle(self):
        mgr = WebSocketManager(heartbeat_interval=0.05)
        ws = AsyncMock()
        await mgr.connect("c1", ws)

        await mgr.start_heartbeat()
        assert mgr._heartbeat_task is not None

        await anyio.sleep(0.15)
        # heartbeat should have sent at least one message
        assert ws.send_text.call_count >= 1

        await mgr.stop_heartbeat()
        assert mgr._heartbeat_task is None

    @pytest.mark.anyio
    async def test_start_heartbeat_idempotent(self):
        mgr = WebSocketManager(heartbeat_interval=1.0)
        await mgr.start_heartbeat()
        task1 = mgr._heartbeat_task
        await mgr.start_heartbeat()
        assert mgr._heartbeat_task is task1
        await mgr.stop_heartbeat()

    @pytest.mark.anyio
    async def test_close_all(self):
        mgr = WebSocketManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await mgr.connect("c1", ws1)
        await mgr.connect("c2", ws2)
        await mgr.close_all()
        assert mgr.connection_count == 0
        ws1.close.assert_awaited_once()
        ws2.close.assert_awaited_once()
