import asyncio
import logging

from src.domain.backtest.interfaces.dashboard_ports import IDashboardDataProvider, IWebSocketManager
from src.domain.backtest.value_objects.dashboard_snapshot import DashboardSnapshot

logger = logging.getLogger(__name__)


class DashboardAppService:
    """Dashboard 应用服务。

    定时收集数据并通过 WebSocket 推送给前端。
    """

    def __init__(
        self,
        data_provider: IDashboardDataProvider,
        ws_manager: IWebSocketManager,
        push_interval: float = 5.0,
    ) -> None:
        self._data_provider = data_provider
        self._ws_manager = ws_manager
        self._push_interval = push_interval
        self._push_task: asyncio.Task | None = None
        self._last_snapshot: DashboardSnapshot | None = None

    @property
    def last_snapshot(self) -> DashboardSnapshot | None:
        return self._last_snapshot

    async def start(self) -> None:
        """启动定时推送。"""
        if self._push_task is not None:
            return
        await self._ws_manager.start_heartbeat()
        self._push_task = asyncio.create_task(self._push_loop())
        logger.info("Dashboard push started (interval=%.1fs)", self._push_interval)

    async def stop(self) -> None:
        """停止定时推送。"""
        if self._push_task is not None:
            self._push_task.cancel()
            try:
                await self._push_task
            except asyncio.CancelledError:
                pass
            self._push_task = None
        await self._ws_manager.stop_heartbeat()
        logger.info("Dashboard push stopped")

    def collect_snapshot(self) -> DashboardSnapshot:
        """收集一次快照（同步，供 REST API 使用）。"""
        snapshot = self._data_provider.get_snapshot()
        self._last_snapshot = snapshot
        return snapshot

    async def push_snapshot(self) -> None:
        """收集并推送一次快照。"""
        snapshot = self.collect_snapshot()
        await self._ws_manager.broadcast({
            "type": "snapshot",
            "data": _snapshot_to_dict(snapshot),
        })

    async def _push_loop(self) -> None:
        """定时推送循环。"""
        while True:
            try:
                await self.push_snapshot()
            except Exception:
                logger.exception("Dashboard push error")
            await asyncio.sleep(self._push_interval)

    def get_equity_curve(self, limit: int = 252) -> list[dict]:
        """获取收益曲线数据。"""
        return [
            {
                "date": p.date.isoformat(),
                "total_asset": p.total_asset,
                "daily_pnl": p.daily_pnl,
                "cumulative_return": p.cumulative_return,
            }
            for p in self._data_provider.get_equity_curve(limit)
        ]


def _snapshot_to_dict(snapshot: DashboardSnapshot) -> dict:
    """将快照转为可 JSON 序列化的 dict。"""
    return {
        "timestamp": snapshot.timestamp.isoformat(),
        "total_asset": snapshot.total_asset,
        "available_cash": snapshot.available_cash,
        "frozen_cash": snapshot.frozen_cash,
        "daily_pnl": snapshot.daily_pnl,
        "daily_pnl_ratio": snapshot.daily_pnl_ratio,
        "total_market_value": snapshot.total_market_value,
        "positions": [
            {
                "ticker": p.ticker,
                "total_volume": p.total_volume,
                "available_volume": p.available_volume,
                "average_cost": p.average_cost,
                "current_price": p.current_price,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
                "pnl_ratio": p.pnl_ratio,
            }
            for p in snapshot.positions
        ],
        "risk_status": {
            "total_position_ratio": snapshot.risk_status.total_position_ratio,
            "max_concentration": snapshot.risk_status.max_concentration,
            "position_count": snapshot.risk_status.position_count,
            "today_drawdown": snapshot.risk_status.today_drawdown,
            "alert_count": snapshot.risk_status.alert_count,
            "is_circuit_breaker_active": snapshot.risk_status.is_circuit_breaker_active,
        },
        "strategies": [
            {
                "strategy_name": s.strategy_name,
                "status": s.status,
                "signal_count_today": s.signal_count_today,
                "last_signal_time": s.last_signal_time.isoformat() if s.last_signal_time else None,
                "daily_pnl": s.daily_pnl,
            }
            for s in snapshot.strategies
        ],
    }
