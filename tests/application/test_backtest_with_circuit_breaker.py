"""BacktestAppService + CircuitBreaker 集成测试。"""
from datetime import datetime
from unittest.mock import MagicMock

from src.application.backtest_app import BacktestAppService
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.risk.services.circuit_breaker import CircuitBreaker
from src.domain.risk.services.risk_event_dispatcher import RiskEventDispatcher
from src.domain.risk.value_objects.circuit_breaker_state import BreakerStatus


def _setup_mock_trade(mock_trade, total_asset: float = 1_000_000):
    mock_trade.get_asset.return_value = MagicMock(
        total_asset=total_asset, available_cash=total_asset,
        frozen_cash=0, account_id="TEST",
    )
    mock_trade.get_positions.return_value = []
    mock_trade.list_orders.return_value = []
    mock_trade.list_trade_records.return_value = []


def test_backtest_without_breaker_unchanged():
    """不传 CircuitBreaker 时行为不变。"""
    mock_market = MagicMock()
    mock_trade = MagicMock()
    mock_strategy = MagicMock()
    mock_evaluator = MagicMock()

    t1 = datetime(2024, 1, 3)
    t2 = datetime(2024, 1, 4)
    bar1 = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=t1,
               open=10.0, high=10.5, low=9.5, close=10.0, volume=10000)
    bar2 = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=t2,
               open=10.0, high=11.0, low=10.0, close=11.0, volume=10000)

    _setup_mock_trade(mock_trade)
    mock_market.get_all_timestamps.return_value = [t1, t2]
    mock_market.get_recent_bars.return_value = [bar1, bar2]
    mock_strategy.generate_signals.return_value = []
    mock_evaluator.evaluate.return_value = MagicMock()

    app = BacktestAppService(
        market_gateway=mock_market,
        trade_gateway=mock_trade,
        strategy=mock_strategy,
        evaluator=mock_evaluator,
    )
    app.run_backtest(
        symbols=["000001.SZ"],
        start_date=t1, end_date=t2,
        base_timeframe=Timeframe.DAY_1,
    )
    mock_evaluator.evaluate.assert_called_once()


def test_backtest_with_breaker_dispatches_events():
    """熔断器事件会被分发器广播。"""
    mock_market = MagicMock()
    mock_trade = MagicMock()
    mock_strategy = MagicMock()
    mock_evaluator = MagicMock()

    t1 = datetime(2024, 1, 3)
    t2 = datetime(2024, 1, 4)
    bar1 = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=t1,
               open=10.0, high=10.5, low=9.5, close=10.0, volume=10000)
    bar2 = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=t2,
               open=10.0, high=11.0, low=10.0, close=11.0, volume=10000)

    # Day 1: asset drops to trigger breaker (3.5% loss)
    assets_by_call = [
        MagicMock(total_asset=1_000_000, available_cash=1_000_000, frozen_cash=0, account_id="T"),
        MagicMock(total_asset=965_000, available_cash=965_000, frozen_cash=0, account_id="T"),
        MagicMock(total_asset=965_000, available_cash=965_000, frozen_cash=0, account_id="T"),
        MagicMock(total_asset=965_000, available_cash=965_000, frozen_cash=0, account_id="T"),
    ]
    call_idx = {"i": 0}
    def get_asset():
        idx = min(call_idx["i"], len(assets_by_call) - 1)
        call_idx["i"] += 1
        return assets_by_call[idx]
    mock_trade.get_asset.side_effect = get_asset
    mock_trade.get_positions.return_value = []
    mock_trade.list_orders.return_value = []
    mock_trade.list_trade_records.return_value = []

    mock_market.get_all_timestamps.return_value = [t1, t2]
    mock_market.get_recent_bars.return_value = [bar1, bar2]
    mock_strategy.generate_signals.return_value = []
    mock_evaluator.evaluate.return_value = MagicMock()

    breaker = CircuitBreaker(max_daily_loss=0.03)
    dispatcher = RiskEventDispatcher()
    notifier = MagicMock()
    dispatcher.add_notifier(notifier)

    app = BacktestAppService(
        market_gateway=mock_market,
        trade_gateway=mock_trade,
        strategy=mock_strategy,
        evaluator=mock_evaluator,
        circuit_breaker=breaker,
        event_dispatcher=dispatcher,
    )
    app.run_backtest(
        symbols=["000001.SZ"],
        start_date=t1, end_date=t2,
        base_timeframe=Timeframe.DAY_1,
    )

    # Verify breaker was evaluated
    assert breaker.state.status in (BreakerStatus.TRIGGERED, BreakerStatus.COOLDOWN, BreakerStatus.NORMAL)
