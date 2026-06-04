from typing import Protocol

from src.domain.backtest.value_objects.dashboard_snapshot import DashboardSnapshot


class IDashboardDataProvider(Protocol):
    """Dashboard 数据提供端口(application 依赖此抽象,infrastructure 实现)。"""

    def get_snapshot(self) -> DashboardSnapshot:
        ...

    def get_equity_curve(self, limit: int) -> list:
        ...


class IWebSocketManager(Protocol):
    """WebSocket 推送端口。"""

    async def start_heartbeat(self) -> None:
        ...

    async def stop_heartbeat(self) -> None:
        ...

    async def broadcast(self, message: dict) -> None:
        ...
