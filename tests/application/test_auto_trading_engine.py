from datetime import datetime
from unittest.mock import MagicMock

from src.application.auto_trading_engine import AutoTradingConfig, AutoTradingEngine, CycleResult
from src.application.anomaly_detector import AnomalyDetector
from src.application.notification_hub import NotificationHub, RateLimiter
from src.application.order_executor import OrderExecutor
from src.application.signal_pipeline import SignalPipeline
from src.application.strategy_runner import DayContext, StrategyRunner
from src.domain.portfolio.entities.order_target import OrderTarget
from src.domain.trade.services.execution_monitor import ExecutionMonitor
from src.domain.trade.value_objects.execution_status import ExecutionStatus
from src.domain.trade.value_objects.order_direction import OrderDirection


class FakeRunner(StrategyRunner):
    def __init__(self, targets: list[OrderTarget] | None = None, prices: dict | None = None) -> None:
        self._targets = targets or []
        self._prices = prices or {}

    def evaluate(self, context: DayContext) -> tuple[list[OrderTarget], dict[str, float]]:
        return self._targets, self._prices


def _make_engine(
    enabled: bool = True,
    targets: list[OrderTarget] | None = None,
    prices: dict | None = None,
) -> tuple[AutoTradingEngine, MagicMock]:
    if targets is None:
        targets = [
            OrderTarget(
                symbol="600000.SH",
                direction=OrderDirection.BUY,
                volume=100,
                price=10.0,
                strategy_name="test",
            ),
        ]
    if prices is None:
        prices = {"600000.SH": 10.0}

    runner = FakeRunner(targets=targets, prices=prices)
    pipeline = SignalPipeline(min_confidence=0.0)

    gateway = MagicMock()
    gateway.place_order.return_value = "order-1"
    risk_chain = MagicMock()
    risk_chain.check.return_value = MagicMock(passed=True, reason="")
    executor = OrderExecutor(gateway, risk_chain)

    monitor = ExecutionMonitor()
    anomaly = AnomalyDetector()

    config = AutoTradingConfig(
        enabled=enabled,
        symbols=["600000.SH"],
        execution_times=["09:35"],
        min_confidence=0.0,
    )

    engine = AutoTradingEngine(
        strategy_runners=[runner],
        signal_pipeline=pipeline,
        order_executor=executor,
        execution_monitor=monitor,
        anomaly_detector=anomaly,
        config=config,
    )
    return engine, gateway


class TestAutoTradingEngine:
    def test_run_cycle_disabled(self):
        engine, gateway = _make_engine(enabled=False)
        result = engine.run_cycle()
        assert result.signals_generated == 0
        assert result.orders_placed == 0
        gateway.place_order.assert_not_called()

    def test_run_cycle_success(self):
        engine, gateway = _make_engine(enabled=True)
        result = engine.run_cycle()

        assert result.orders_placed == 1
        assert result.orders_rejected == 0
        gateway.place_order.assert_called_once()

    def test_run_cycle_returns_cycle_result(self):
        engine, _ = _make_engine(enabled=True)
        result = engine.run_cycle()
        assert isinstance(result, CycleResult)
        assert result.cycle_time is not None

    def test_is_running_false_by_default(self):
        engine, _ = _make_engine()
        assert not engine.is_running

    def test_get_cycle_results(self):
        engine, _ = _make_engine(enabled=True)
        engine.run_cycle()
        results = engine.get_cycle_results()
        assert len(results) == 1

    def test_is_trading_hour(self):
        engine, _ = _make_engine()
        # During trading hours
        assert engine._is_trading_hour(datetime(2025, 1, 1, 10, 0))
        # Outside trading hours
        assert not engine._is_trading_hour(datetime(2025, 1, 1, 16, 0))
        assert not engine._is_trading_hour(datetime(2025, 1, 1, 8, 0))
