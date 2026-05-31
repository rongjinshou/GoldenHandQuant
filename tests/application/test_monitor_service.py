from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.application.monitor_service import MonitorService
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe


def _make_bar(symbol: str, close: float) -> Bar:
    return Bar(
        symbol=symbol, timeframe=Timeframe.DAY_1,
        timestamp=datetime(2026, 1, 1), open=close, high=close,
        low=close, close=close, volume=1000,
    )


class TestMonitorService:
    def _make_service(self):
        account_gw = MagicMock()
        market_gw = MagicMock()
        account_gw.get_asset.return_value = Asset(
            account_id="test", total_asset=1_000_000, available_cash=500_000,
        )
        account_gw.get_positions.return_value = [
            Position(
                account_id="test", ticker="600000.SH",
                total_volume=500, available_volume=500, average_cost=12.0,
            ),
        ]
        market_gw.get_recent_bars.return_value = [_make_bar("600000.SH", 13.0)]
        service = MonitorService(
            account_gateway=account_gw,
            market_gateway=market_gw,
            yesterday_asset=990_000,
        )
        return service, account_gw, market_gw

    def test_take_snapshot_should_return_valid_snapshot(self):
        service, _, _ = self._make_service()
        snapshot = service.take_snapshot()
        assert snapshot.asset.total_asset == 1_000_000
        assert len(snapshot.positions) == 1
        assert snapshot.positions[0].current_price == 13.0
        assert snapshot.positions[0].unrealized_pnl == 500.0  # (13-12)*500

    def test_take_snapshot_should_calculate_risk_metrics(self):
        service, _, _ = self._make_service()
        snapshot = service.take_snapshot()
        # market_value = 500 * 13 = 6500, total_asset = 1_000_000
        assert snapshot.risk_metrics.total_position_ratio == pytest.approx(0.0065, abs=0.001)
        assert snapshot.risk_metrics.position_count == 1

    def test_take_snapshot_no_market_data_should_use_cost(self):
        service, _, market_gw = self._make_service()
        market_gw.get_recent_bars.return_value = []
        snapshot = service.take_snapshot()
        # 无行情时应使用成本价
        assert snapshot.positions[0].current_price == 12.0

    def test_take_snapshot_should_include_today_pnl(self):
        service, _, _ = self._make_service()
        snapshot = service.take_snapshot()
        assert snapshot.today_pnl == 10_000  # 1_000_000 - 990_000
