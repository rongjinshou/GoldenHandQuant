from datetime import datetime
from unittest.mock import MagicMock

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.backtest.value_objects.dashboard_snapshot import StrategyStatus
from src.infrastructure.web.dashboard_data_provider import DashboardDataProvider


def _make_account_gateway(asset=None, positions=None):
    gw = MagicMock()
    gw.get_asset.return_value = asset
    gw.get_positions.return_value = positions or []
    return gw


def _make_market_gateway(price_map=None):
    gw = MagicMock()

    def get_recent_bars(symbol, timeframe, limit):
        price = (price_map or {}).get(symbol, 10.0)
        bar = MagicMock(spec=Bar)
        bar.close = price
        return [bar]

    gw.get_recent_bars.side_effect = get_recent_bars
    return gw


class TestDashboardDataProvider:
    def test_get_snapshot_no_asset(self):
        gw = _make_account_gateway()
        provider = DashboardDataProvider(gw, _make_market_gateway())
        snapshot = provider.get_snapshot()
        assert snapshot.total_asset == 0.0
        assert snapshot.positions == []

    def test_get_snapshot_with_positions(self):
        asset = Asset(account_id="test", total_asset=100000, available_cash=50000, frozen_cash=0)
        positions = [
            Position(account_id="test", ticker="600000.SH", total_volume=1000, available_volume=500, average_cost=10.0),
            Position(account_id="test", ticker="000001.SZ", total_volume=500, available_volume=500, average_cost=20.0),
        ]
        gw = _make_account_gateway(asset=asset, positions=positions)
        market_gw = _make_market_gateway({"600000.SH": 12.0, "000001.SZ": 18.0})

        provider = DashboardDataProvider(gw, market_gw)
        snapshot = provider.get_snapshot()

        assert snapshot.total_asset == 100000
        assert len(snapshot.positions) == 2
        assert snapshot.positions[0].ticker == "600000.SH"
        assert snapshot.positions[0].current_price == 12.0
        assert snapshot.positions[0].unrealized_pnl == 2000.0
        assert snapshot.total_market_value == 12.0 * 1000 + 18.0 * 500

    def test_daily_pnl_calculation(self):
        asset = Asset(account_id="test", total_asset=101000, available_cash=51000, frozen_cash=0)
        gw = _make_account_gateway(asset=asset)
        provider = DashboardDataProvider(gw, _make_market_gateway(), yesterday_asset=100000)

        snapshot = provider.get_snapshot()
        assert snapshot.daily_pnl == 1000.0
        assert abs(snapshot.daily_pnl_ratio - 0.01) < 1e-9

    def test_daily_pnl_zero_yesterday(self):
        asset = Asset(account_id="test", total_asset=100000, available_cash=100000, frozen_cash=0)
        gw = _make_account_gateway(asset=asset)
        provider = DashboardDataProvider(gw, _make_market_gateway())

        snapshot = provider.get_snapshot()
        assert snapshot.daily_pnl == 0.0
        assert snapshot.daily_pnl_ratio == 0.0

    def test_risk_status_calculation(self):
        asset = Asset(account_id="test", total_asset=100000, available_cash=0, frozen_cash=0)
        positions = [
            Position(account_id="test", ticker="600000.SH", total_volume=1000, available_volume=1000, average_cost=10.0),
        ]
        gw = _make_account_gateway(asset=asset, positions=positions)
        market_gw = _make_market_gateway({"600000.SH": 50.0})

        provider = DashboardDataProvider(gw, market_gw)
        snapshot = provider.get_snapshot()

        assert snapshot.risk_status.position_count == 1
        assert snapshot.risk_status.total_position_ratio == 0.5  # 50000/100000
        assert snapshot.risk_status.max_concentration == 0.5

    def test_get_equity_curve(self):
        asset1 = Asset(account_id="test", total_asset=100000, available_cash=100000, frozen_cash=0)
        asset2 = Asset(account_id="test", total_asset=101000, available_cash=101000, frozen_cash=0)

        gw = MagicMock()
        gw.get_asset.side_effect = [asset1, asset2]
        gw.get_positions.return_value = []

        provider = DashboardDataProvider(gw, _make_market_gateway())
        provider.get_snapshot()
        provider.get_snapshot()

        curve = provider.get_equity_curve()
        assert len(curve) == 2
        assert curve[0].total_asset == 100000
        assert curve[1].total_asset == 101000

    def test_update_strategy_statuses(self):
        gw = _make_account_gateway()
        provider = DashboardDataProvider(gw, _make_market_gateway())
        provider.update_strategy_statuses([
            StrategyStatus(strategy_name="DualMA", status="running", signal_count_today=3),
        ])

        snapshot = provider.get_snapshot()
        assert len(snapshot.strategies) == 1
        assert snapshot.strategies[0].strategy_name == "DualMA"

    def test_set_yesterday_asset(self):
        gw = _make_account_gateway()
        provider = DashboardDataProvider(gw, _make_market_gateway())
        provider.set_yesterday_asset(95000)

        asset = Asset(account_id="test", total_asset=100000, available_cash=100000, frozen_cash=0)
        gw.get_asset.return_value = asset

        snapshot = provider.get_snapshot()
        assert snapshot.daily_pnl == 5000.0
