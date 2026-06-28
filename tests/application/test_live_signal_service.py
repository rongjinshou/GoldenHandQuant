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


def test_scan_cross_sectional_via_decision_core(monkeypatch):
    """截面 scan(micro_value) 经决策核心 CrossSectionalStrategyRunner 产 SignalDisplay。

    复用 test_strategy_runner_lookahead 的 fixture 模式: MockMarketGateway 装含
    fundamental 的截面 bars + FundamentalRegistry。micro_value 仅周二调仓 + 内部用
    datetime.now() → 冻结 now() 为固定周二(2024-06-11, 非 1/4 月)保证确定性。
    """
    from src.application import live_signal_service as lss
    from src.domain.market.services.fundamental_registry import FundamentalRegistry
    from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
    from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
    from src.infrastructure.mock.mock_market import MockMarketGateway
    from src.infrastructure.mock.mock_trade import MockTradeGateway

    fixed_now = datetime(2024, 6, 11, 10, 0, 0)  # 周二(weekday()==1), 6 月

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(lss, "datetime", _FixedDatetime)

    symbols = ["000001.SZ", "000002.SZ", "000003.SZ"]
    market = MockMarketGateway()
    for i, sym in enumerate(symbols):
        bars = []
        for day in range(5, 12):  # 06-05 .. 06-11
            close = 10.0 + i
            bars.append(Bar(
                symbol=sym, timeframe=Timeframe.DAY_1,
                timestamp=datetime(2024, 6, day),
                open=close * 0.99, high=close * 1.02, low=close * 0.98,
                close=close, volume=1_000_000, prev_close=close * 0.99,
            ))
        market.add_bars(sym, bars)
    market.set_current_time(datetime(2024, 6, 11, 23, 59))

    registry = FundamentalRegistry()
    for i, sym in enumerate(symbols):
        registry.add(FundamentalSnapshot(
            symbol=sym, date=fixed_now, name=f"Co{sym}",
            list_date=datetime(2000, 1, 1), market_cap=1e9 + i * 1e8,
            roe_ttm=0.15, ocf_ttm=1e8,
        ))

    trade = MockTradeGateway(market, initial_capital=1_000_000)
    account_gw = MagicMock()
    account_gw.get_asset.return_value = Asset(
        account_id="t", total_asset=1_000_000, available_cash=1_000_000,
    )
    account_gw.get_positions.return_value = []

    service = LiveSignalService(
        market_gateway=market, account_gateway=account_gw, trade_gateway=trade,
        sizer=EqualWeightSizer(n_symbols=len(symbols)),
        fundamental_registry=registry,
    )

    displays = service.scan(strategy_name="micro_value", symbols=symbols)

    assert len(displays) >= 1
    for d in displays:
        assert "决策核心" in d.reason
        assert d.confidence_score == 1.0
        assert d.suggested_volume > 0
        assert d.suggested_price > 0
        assert d.required_capital > 0
        assert d.direction == SignalDirection.BUY


def test_scan_cross_sectional_invokes_decision_core(monkeypatch):
    """截面 scan 路径必走 CrossSectionalStrategyRunner.evaluate(DayContext), 并把
    OrderTarget 映射为 SignalDisplay(reason 含 '决策核心', confidence==1.0)。

    用 fake runner 注入, 与策略内部细节解耦, 确定性验证分流+映射。
    """
    from src.application import strategy_runner as sr
    from src.application.strategy_runner import DayContext
    from src.domain.portfolio.entities.order_target import OrderTarget
    from src.domain.trade.value_objects.order_direction import OrderDirection

    captured: dict = {}
    target = OrderTarget(
        symbol="000001.SZ", direction=OrderDirection.BUY,
        volume=300, price=12.0, strategy_name="MicroValueStrategy",
    )

    class _FakeRunner:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def evaluate(self, context):
            captured["context"] = context
            return [target], {"000001.SZ": 12.5}

    monkeypatch.setattr(sr, "CrossSectionalStrategyRunner", _FakeRunner)

    market = MagicMock()
    account_gw = MagicMock()
    account_gw.get_asset.return_value = Asset(
        account_id="t", total_asset=1_000_000, available_cash=1_000_000,
    )
    account_gw.get_positions.return_value = []
    trade = MagicMock()
    registry = object()  # sentinel

    service = LiveSignalService(
        market_gateway=market, account_gateway=account_gw, trade_gateway=trade,
        fundamental_registry=registry,
    )

    displays = service.scan(strategy_name="micro_value", symbols=["000001.SZ"])

    # 走了截面分流 → 构造了决策核心 runner, 注入了 fundamental_registry + DayContext
    assert captured["init"]["fundamental_registry"] is registry
    assert isinstance(captured["context"], DayContext)
    assert captured["context"].symbols == ["000001.SZ"]
    assert captured["context"].base_timeframe == Timeframe.DAY_1
    # OrderTarget → SignalDisplay 映射
    assert len(displays) == 1
    d = displays[0]
    assert d.symbol == "000001.SZ"
    assert d.direction == SignalDirection.BUY
    assert d.current_price == 12.5      # prices.get(symbol)
    assert d.suggested_price == 12.0    # target.price
    assert d.suggested_volume == 300
    assert d.required_capital == round(12.0 * 300, 2)
    assert "决策核心" in d.reason
    assert d.strategy_name == "MicroValueStrategy"
    assert d.confidence_score == 1.0
