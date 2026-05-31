import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.domain.account.entities.asset import Asset
from src.domain.backtest.value_objects.dashboard_snapshot import DashboardSnapshot
from src.infrastructure.web.dashboard_data_provider import DashboardDataProvider
from src.infrastructure.web.websocket_manager import WebSocketManager
from src.application.dashboard_app import DashboardAppService, _snapshot_to_dict


def _make_snapshot(**kwargs) -> DashboardSnapshot:
    defaults = {
        "timestamp": datetime(2024, 6, 1, 10, 0, 0),
        "total_asset": 100000.0,
        "available_cash": 50000.0,
        "frozen_cash": 0.0,
        "daily_pnl": 1000.0,
        "daily_pnl_ratio": 0.01,
        "total_market_value": 50000.0,
    }
    defaults.update(kwargs)
    return DashboardSnapshot(**defaults)


class TestDashboardAppService:
    def test_collect_snapshot(self):
        provider = MagicMock(spec=DashboardDataProvider)
        expected = _make_snapshot()
        provider.get_snapshot.return_value = expected

        ws_mgr = MagicMock(spec=WebSocketManager)
        service = DashboardAppService(provider, ws_mgr)

        snapshot = service.collect_snapshot()
        assert snapshot is expected
        assert service.last_snapshot is expected

    @pytest.mark.anyio
    async def test_push_snapshot(self):
        provider = MagicMock(spec=DashboardDataProvider)
        provider.get_snapshot.return_value = _make_snapshot()
        provider.get_equity_curve.return_value = []

        ws_mgr = AsyncMock(spec=WebSocketManager)
        service = DashboardAppService(provider, ws_mgr)

        await service.push_snapshot()
        ws_mgr.broadcast.assert_awaited_once()
        call_args = ws_mgr.broadcast.call_args[0][0]
        assert call_args["type"] == "snapshot"
        assert call_args["data"]["total_asset"] == 100000.0

    @pytest.mark.anyio
    async def test_start_stop(self):
        provider = MagicMock(spec=DashboardDataProvider)
        ws_mgr = MagicMock(spec=WebSocketManager)
        ws_mgr.start_heartbeat = AsyncMock()
        ws_mgr.stop_heartbeat = AsyncMock()

        service = DashboardAppService(provider, ws_mgr, push_interval=10.0)
        await service.start()
        assert service._push_task is not None

        await service.stop()
        assert service._push_task is None
        ws_mgr.start_heartbeat.assert_awaited_once()
        ws_mgr.stop_heartbeat.assert_awaited_once()

    @pytest.mark.anyio
    async def test_start_idempotent(self):
        provider = MagicMock(spec=DashboardDataProvider)
        ws_mgr = MagicMock(spec=WebSocketManager)
        ws_mgr.start_heartbeat = AsyncMock()
        ws_mgr.stop_heartbeat = AsyncMock()

        service = DashboardAppService(provider, ws_mgr, push_interval=10.0)
        await service.start()
        task1 = service._push_task
        await service.start()
        assert service._push_task is task1
        await service.stop()

    def test_get_equity_curve_empty(self):
        provider = MagicMock(spec=DashboardDataProvider)
        provider.get_equity_curve.return_value = []
        ws_mgr = MagicMock(spec=WebSocketManager)
        service = DashboardAppService(provider, ws_mgr)

        assert service.get_equity_curve() == []

    def test_get_equity_curve_with_data(self):
        from src.domain.backtest.value_objects.dashboard_snapshot import EquityCurvePoint

        provider = MagicMock(spec=DashboardDataProvider)
        provider.get_equity_curve.return_value = [
            EquityCurvePoint(
                date=datetime(2024, 6, 1),
                total_asset=100000.0,
                daily_pnl=0.0,
                cumulative_return=0.0,
            ),
            EquityCurvePoint(
                date=datetime(2024, 6, 2),
                total_asset=101000.0,
                daily_pnl=1000.0,
                cumulative_return=0.01,
            ),
        ]
        ws_mgr = MagicMock(spec=WebSocketManager)
        service = DashboardAppService(provider, ws_mgr)

        curve = service.get_equity_curve()
        assert len(curve) == 2
        assert curve[0]["total_asset"] == 100000.0
        assert curve[1]["cumulative_return"] == 0.01


class TestSnapshotToDict:
    def test_basic_fields(self):
        snapshot = _make_snapshot()
        d = _snapshot_to_dict(snapshot)
        assert d["total_asset"] == 100000.0
        assert d["daily_pnl"] == 1000.0
        assert isinstance(d["timestamp"], str)

    def test_positions_serialization(self):
        from src.domain.backtest.value_objects.dashboard_snapshot import PositionSnapshot

        snapshot = _make_snapshot(positions=[
            PositionSnapshot(
                ticker="600000.SH",
                total_volume=1000,
                available_volume=500,
                average_cost=10.0,
                current_price=12.0,
                market_value=12000.0,
                unrealized_pnl=2000.0,
                pnl_ratio=0.2,
            ),
        ])
        d = _snapshot_to_dict(snapshot)
        assert len(d["positions"]) == 1
        assert d["positions"][0]["ticker"] == "600000.SH"

    def test_risk_status_serialization(self):
        snapshot = _make_snapshot()
        d = _snapshot_to_dict(snapshot)
        assert "total_position_ratio" in d["risk_status"]
        assert "is_circuit_breaker_active" in d["risk_status"]

    def test_strategies_serialization(self):
        from src.domain.backtest.value_objects.dashboard_snapshot import StrategyStatus

        snapshot = _make_snapshot(strategies=[
            StrategyStatus(strategy_name="DualMA", status="running"),
        ])
        d = _snapshot_to_dict(snapshot)
        assert len(d["strategies"]) == 1
        assert d["strategies"][0]["strategy_name"] == "DualMA"
