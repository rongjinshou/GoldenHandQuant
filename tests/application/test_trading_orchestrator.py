"""TradingOrchestrator 测试。"""

from datetime import datetime
from unittest.mock import MagicMock

from src.application.anomaly_detector import AnomalyDetector
from src.application.order_executor import OrderExecutor
from src.application.signal_pipeline import SignalPipeline
from src.application.strategy_runner import DayContext, StrategyRunner
from src.application.trading_orchestrator import CycleResult, TradingOrchestrator
from src.domain.portfolio.entities.order_target import OrderTarget
from src.domain.trade.services.execution_monitor import ExecutionMonitor
from src.domain.trade.value_objects.order_direction import OrderDirection


class FakeRunner(StrategyRunner):
    def __init__(self, targets, prices=None, strategy_name="test"):
        self._targets = targets
        self._prices = prices or {}
        self.strategy_name = strategy_name

    def evaluate(self, context):
        return self._targets, self._prices


class TestTradingOrchestrator:
    def _make_orchestrator(self, targets=None, prices=None, strategy_name="test"):
        if targets is None:
            targets = [OrderTarget(
                symbol="600000.SH", direction=OrderDirection.BUY,
                volume=100, price=10.0, strategy_name=strategy_name,
            )]
        if prices is None:
            prices = {"600000.SH": 10.0}

        runner = FakeRunner(targets, prices, strategy_name=strategy_name)
        pipeline = SignalPipeline(min_confidence=0.0)
        gateway = MagicMock()
        gateway.place_order.return_value = "order-1"
        risk_chain = MagicMock()
        risk_chain.check.return_value = MagicMock(passed=True, reason="")
        executor = OrderExecutor(gateway, risk_chain)
        monitor = ExecutionMonitor()
        anomaly = AnomalyDetector()

        return TradingOrchestrator(
            strategy_runners=[runner],
            signal_pipeline=pipeline,
            order_executor=executor,
            execution_monitor=monitor,
            anomaly_detector=anomaly,
            max_orders_per_cycle=20,
            symbols=["600000.SH"],
        ), gateway

    def test_execute_cycle_returns_cycle_result(self):
        orchestrator, _ = self._make_orchestrator()
        result = orchestrator.execute_cycle(datetime(2025, 1, 1, 10, 0))
        assert isinstance(result, CycleResult)

    def test_execute_cycle_success(self):
        orchestrator, gateway = self._make_orchestrator()
        result = orchestrator.execute_cycle(datetime(2025, 1, 1, 10, 0))
        assert result.orders_placed == 1
        gateway.place_order.assert_called_once()

    def test_execute_cycle_with_paused_strategy(self):
        # Orchestrator with pause_manager that pauses all strategies
        targets = [OrderTarget(
            symbol="600000.SH", direction=OrderDirection.BUY,
            volume=100, price=10.0, strategy_name="paused_strategy",
        )]
        orchestrator, gateway = self._make_orchestrator(targets=targets, strategy_name="paused_strategy")

        # Add a pause_manager that pauses the strategy
        pause_manager = MagicMock()
        pause_manager.is_strategy_paused.return_value = True
        pause_manager.is_all_paused = False
        orchestrator._pause_manager = pause_manager

        result = orchestrator.execute_cycle(datetime(2025, 1, 1, 10, 0))
        assert result.orders_placed == 0

    def test_execute_cycle_global_pause(self):
        orchestrator, gateway = self._make_orchestrator()
        pause_manager = MagicMock()
        pause_manager.is_strategy_paused.return_value = False
        pause_manager.is_all_paused = True
        orchestrator._pause_manager = pause_manager

        result = orchestrator.execute_cycle(datetime(2025, 1, 1, 10, 0))
        assert result.orders_placed == 0
        gateway.place_order.assert_not_called()

    def test_max_orders_per_cycle_respected(self):
        targets = [
            OrderTarget(
                symbol=f"60000{i}.SH", direction=OrderDirection.BUY,
                volume=100, price=10.0, strategy_name="test",
            )
            for i in range(5)
        ]
        prices = {f"60000{i}.SH": 10.0 for i in range(5)}
        orchestrator, gateway = self._make_orchestrator(targets=targets, prices=prices)
        orchestrator._max_orders_per_cycle = 2

        result = orchestrator.execute_cycle(datetime(2025, 1, 1, 10, 0))
        assert result.orders_placed <= 2
