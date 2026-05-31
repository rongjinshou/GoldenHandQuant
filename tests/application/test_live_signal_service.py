from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.application.live_signal_service import LiveSignalService, SignalDisplay
from src.domain.account.entities.asset import Asset
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.value_objects.signal_direction import SignalDirection


def _make_bars(symbol: str, prices: list[float]) -> list[Bar]:
    bars = []
    base = datetime(2026, 1, 1) - timedelta(days=len(prices))
    for i, p in enumerate(prices):
        bars.append(Bar(
            symbol=symbol, timeframe=Timeframe.DAY_1,
            timestamp=base + timedelta(days=i),
            open=p, high=p, low=p, close=p, volume=1000,
        ))
    return bars


class TestLiveSignalService:
    def _make_service(self) -> tuple[LiveSignalService, MagicMock, MagicMock, MagicMock]:
        market_gw = MagicMock()
        account_gw = MagicMock()
        trade_gw = MagicMock()

        account_gw.get_asset.return_value = Asset(
            account_id="test_acc", total_asset=1_000_000, available_cash=500_000,
        )
        account_gw.get_positions.return_value = []

        service = LiveSignalService(
            market_gateway=market_gw,
            account_gateway=account_gw,
            trade_gateway=trade_gw,
        )
        return service, market_gw, account_gw, trade_gw

    def test_scan_bar_strategy_should_return_signal_displays(self):
        service, market_gw, _, _ = self._make_service()
        market_gw.get_recent_bars.return_value = _make_bars("600000.SH", [10]*10 + [20])

        displays = service.scan(strategy_name="dual_ma", symbols=["600000.SH"])

        assert len(displays) == 1
        d = displays[0]
        assert d.symbol == "600000.SH"
        assert d.direction == SignalDirection.BUY
        assert d.current_price == 20.0
        assert d.suggested_volume > 0
        assert d.required_capital > 0
        assert "Golden Cross" in d.reason

    def test_scan_no_signals_should_return_empty(self):
        service, market_gw, _, _ = self._make_service()
        market_gw.get_recent_bars.return_value = _make_bars("600000.SH", [10]*20)

        displays = service.scan(strategy_name="dual_ma", symbols=["600000.SH"])

        assert len(displays) == 0

    def test_scan_insufficient_data_should_skip(self):
        service, market_gw, _, _ = self._make_service()
        market_gw.get_recent_bars.return_value = _make_bars("600000.SH", [10]*5)

        displays = service.scan(strategy_name="dual_ma", symbols=["600000.SH"])

        assert len(displays) == 0

    def test_scan_no_market_data_should_skip(self):
        service, market_gw, _, _ = self._make_service()
        market_gw.get_recent_bars.return_value = []

        displays = service.scan(strategy_name="dual_ma", symbols=["600000.SH"])

        assert len(displays) == 0

    def test_place_confirmed_orders_should_call_trade_gateway(self):
        service, _, _, trade_gw = self._make_service()
        trade_gw.place_order.return_value = "order_123"

        display = SignalDisplay(
            symbol="600000.SH", direction=SignalDirection.BUY,
            current_price=12.50, suggested_price=12.52,
            suggested_volume=500, required_capital=6260.0,
            reason="Golden Cross", strategy_name="DualMaStrategy",
            confidence_score=1.0,
        )

        results = service.place_confirmed_orders([display])

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].order_id == "order_123"
        trade_gw.place_order.assert_called_once()

    def test_place_confirmed_orders_failure_should_return_error(self):
        service, _, _, trade_gw = self._make_service()
        from src.domain.trade.exceptions import OrderSubmitError
        trade_gw.place_order.side_effect = OrderSubmitError("QMT error")

        display = SignalDisplay(
            symbol="600000.SH", direction=SignalDirection.BUY,
            current_price=12.50, suggested_price=12.52,
            suggested_volume=500, required_capital=6260.0,
            reason="test", strategy_name="test", confidence_score=1.0,
        )

        results = service.place_confirmed_orders([display])

        assert len(results) == 1
        assert results[0].success is False
        assert "QMT error" in results[0].error_message
