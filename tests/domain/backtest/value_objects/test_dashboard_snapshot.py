from datetime import datetime

from src.domain.backtest.value_objects.dashboard_snapshot import (
    DashboardSnapshot,
    EquityCurvePoint,
    PositionSnapshot,
    RiskStatus,
    StrategyStatus,
)


class TestPositionSnapshot:
    def test_create_position_snapshot(self):
        ps = PositionSnapshot(
            ticker="600000.SH",
            total_volume=1000,
            available_volume=500,
            average_cost=10.0,
            current_price=12.0,
            market_value=12000.0,
            unrealized_pnl=2000.0,
            pnl_ratio=0.2,
        )
        assert ps.ticker == "600000.SH"
        assert ps.total_volume == 1000
        assert ps.pnl_ratio == 0.2

    def test_frozen_immutable(self):
        ps = PositionSnapshot(
            ticker="600000.SH",
            total_volume=1000,
            available_volume=500,
            average_cost=10.0,
            current_price=12.0,
            market_value=12000.0,
            unrealized_pnl=2000.0,
            pnl_ratio=0.2,
        )
        import pytest
        with pytest.raises(AttributeError):
            ps.ticker = "000001.SZ"


class TestRiskStatus:
    def test_default_values(self):
        rs = RiskStatus(
            total_position_ratio=0.5,
            max_concentration=0.3,
            position_count=3,
        )
        assert rs.today_drawdown == 0.0
        assert rs.alert_count == 0
        assert rs.is_circuit_breaker_active is False

    def test_custom_values(self):
        rs = RiskStatus(
            total_position_ratio=0.8,
            max_concentration=0.5,
            position_count=5,
            today_drawdown=0.02,
            alert_count=2,
            is_circuit_breaker_active=True,
        )
        assert rs.today_drawdown == 0.02
        assert rs.alert_count == 2
        assert rs.is_circuit_breaker_active is True


class TestStrategyStatus:
    def test_default_values(self):
        ss = StrategyStatus(strategy_name="DualMA", status="running")
        assert ss.signal_count_today == 0
        assert ss.last_signal_time is None
        assert ss.daily_pnl == 0.0

    def test_with_values(self):
        now = datetime.now()
        ss = StrategyStatus(
            strategy_name="MicroValue",
            status="paused",
            signal_count_today=5,
            last_signal_time=now,
            daily_pnl=1500.0,
        )
        assert ss.signal_count_today == 5
        assert ss.last_signal_time == now
        assert ss.daily_pnl == 1500.0


class TestDashboardSnapshot:
    def _make_snapshot(self, **kwargs) -> DashboardSnapshot:
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

    def test_default_positions_empty(self):
        snapshot = self._make_snapshot()
        assert snapshot.positions == []
        assert snapshot.strategies == []

    def test_with_positions(self):
        ps = PositionSnapshot(
            ticker="600000.SH",
            total_volume=1000,
            available_volume=500,
            average_cost=10.0,
            current_price=12.0,
            market_value=12000.0,
            unrealized_pnl=2000.0,
            pnl_ratio=0.2,
        )
        snapshot = self._make_snapshot(positions=[ps])
        assert len(snapshot.positions) == 1
        assert snapshot.positions[0].ticker == "600000.SH"

    def test_frozen_immutable(self):
        snapshot = self._make_snapshot()
        import pytest
        with pytest.raises(AttributeError):
            snapshot.total_asset = 999999.0


class TestEquityCurvePoint:
    def test_create(self):
        point = EquityCurvePoint(
            date=datetime(2024, 6, 1),
            total_asset=101000.0,
            daily_pnl=1000.0,
            cumulative_return=0.01,
        )
        assert point.total_asset == 101000.0
        assert point.cumulative_return == 0.01
