"""StrategyRunner + CircuitBreaker 集成测试。"""
from unittest.mock import MagicMock

from src.application.strategy_runner import SingleStrategyRunner
from src.domain.risk.services.circuit_breaker import CircuitBreaker
from src.domain.risk.value_objects.circuit_breaker_state import BreakerStatus, CircuitBreakerState
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.trade.value_objects.order_direction import OrderDirection


def _make_runner(circuit_breaker=None):
    strategy = MagicMock()
    sizer = MagicMock()
    market = MagicMock()
    trade = MagicMock()

    runner = SingleStrategyRunner(
        strategy=strategy,
        sizer=sizer,
        market_gateway=market,
        trade_gateway=trade,
        circuit_breaker=circuit_breaker,
    )
    return runner, strategy, sizer, market, trade


def test_triggered_breaker_returns_empty():
    breaker = CircuitBreaker()
    breaker._state = CircuitBreakerState(
        status=BreakerStatus.TRIGGERED,
        trigger_reason="test",
    )
    runner, *_ = _make_runner(circuit_breaker=breaker)

    context = MagicMock()
    targets, prices = runner.evaluate(context)

    assert targets == []
    assert prices == {}


def test_normal_breaker_allows_signals():
    breaker = CircuitBreaker()
    runner, strategy, sizer, market, trade = _make_runner(circuit_breaker=breaker)

    from src.domain.market.value_objects.bar import Bar
    from src.domain.market.value_objects.timeframe import Timeframe
    from datetime import datetime

    bar_t1 = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1,
                 timestamp=datetime(2024, 1, 2),
                 open=9.5, high=10.0, low=9.0, close=9.5, volume=10000)
    bar_t = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1,
                timestamp=datetime(2024, 1, 3),
                open=10.0, high=10.5, low=9.5, close=10.0, volume=10000)
    market.get_recent_bars.return_value = [bar_t1, bar_t]

    signal = MagicMock()
    signal.symbol = "000001.SZ"
    signal.direction = SignalDirection.BUY
    signal.strategy_name = "test"
    strategy.generate_signals.return_value = [signal]

    trade.get_positions.return_value = []
    trade.get_asset.return_value = MagicMock(total_asset=1_000_000)

    sizer.calculate_target.return_value = 100

    context = MagicMock()
    context.symbols = ["000001.SZ"]
    context.current_time = datetime(2024, 1, 3)
    targets, prices = runner.evaluate(context)

    assert len(targets) == 1


def test_no_breaker_allows_signals():
    runner, strategy, sizer, market, trade = _make_runner(circuit_breaker=None)

    from src.domain.market.value_objects.bar import Bar
    from src.domain.market.value_objects.timeframe import Timeframe
    from datetime import datetime

    bar_t1 = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1,
                 timestamp=datetime(2024, 1, 2),
                 open=9.5, high=10.0, low=9.0, close=9.5, volume=10000)
    bar_t = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1,
                timestamp=datetime(2024, 1, 3),
                open=10.0, high=10.5, low=9.5, close=10.0, volume=10000)
    market.get_recent_bars.return_value = [bar_t1, bar_t]

    signal = MagicMock()
    signal.symbol = "000001.SZ"
    signal.direction = SignalDirection.BUY
    signal.strategy_name = "test"
    strategy.generate_signals.return_value = [signal]

    trade.get_positions.return_value = []
    trade.get_asset.return_value = MagicMock(total_asset=1_000_000)

    sizer.calculate_target.return_value = 100

    context = MagicMock()
    context.symbols = ["000001.SZ"]
    context.current_time = datetime(2024, 1, 3)
    targets, prices = runner.evaluate(context)

    assert len(targets) == 1
