from datetime import datetime, timedelta

from src.domain.trade.services.execution_monitor import ExecutionMonitor
from src.domain.trade.value_objects.execution_record import ExecutionRecord
from src.domain.trade.value_objects.execution_status import ExecutionStatus
from src.domain.trade.value_objects.health_status import HealthStatus
from src.domain.trade.value_objects.order_direction import OrderDirection


def _make_record(
    direction: OrderDirection = OrderDirection.BUY,
    status: ExecutionStatus = ExecutionStatus.FILLED,
    target_price: float = 10.0,
    actual_price: float = 10.01,
    volume: int = 100,
    submitted_at: datetime | None = None,
    filled_at: datetime | None = None,
    slippage: float = 0.001,
) -> ExecutionRecord:
    now = datetime.now()
    return ExecutionRecord(
        order_id="test-order",
        symbol="600000.SH",
        direction=direction,
        target_price=target_price,
        target_volume=volume,
        actual_price=actual_price,
        actual_volume=volume,
        slippage=slippage,
        status=status,
        submitted_at=submitted_at or now,
        filled_at=filled_at or (now + timedelta(seconds=5)),
    )


class TestExecutionMonitor:
    def test_record_and_get_stats_empty(self):
        monitor = ExecutionMonitor()
        stats = monitor.get_stats()
        assert stats.total_orders == 0
        assert stats.success_rate == 0.0

    def test_record_and_get_stats_with_data(self):
        monitor = ExecutionMonitor()
        monitor.record(_make_record(status=ExecutionStatus.FILLED, slippage=0.001))
        monitor.record(_make_record(status=ExecutionStatus.FILLED, slippage=0.002))
        monitor.record(_make_record(status=ExecutionStatus.FAILED))

        stats = monitor.get_stats()
        assert stats.total_orders == 3
        assert stats.successful_orders == 2
        assert stats.failed_orders == 1
        assert abs(stats.success_rate - 2 / 3) < 0.01

    def test_check_health_healthy(self):
        monitor = ExecutionMonitor()
        for _ in range(10):
            monitor.record(_make_record(status=ExecutionStatus.FILLED, slippage=0.001))
        assert monitor.check_health() == HealthStatus.HEALTHY

    def test_check_health_warning_low_success_rate(self):
        monitor = ExecutionMonitor()
        for _ in range(8):
            monitor.record(_make_record(status=ExecutionStatus.FILLED))
        for _ in range(2):
            monitor.record(_make_record(status=ExecutionStatus.FAILED))
        # success rate = 80% -> WARNING
        assert monitor.check_health() == HealthStatus.WARNING

    def test_check_health_critical_low_success_rate(self):
        monitor = ExecutionMonitor()
        for _ in range(7):
            monitor.record(_make_record(status=ExecutionStatus.FILLED))
        for _ in range(3):
            monitor.record(_make_record(status=ExecutionStatus.FAILED))
        # success rate = 70% -> CRITICAL
        assert monitor.check_health() == HealthStatus.CRITICAL

    def test_check_health_warning_high_slippage(self):
        monitor = ExecutionMonitor()
        for _ in range(5):
            monitor.record(_make_record(
                direction=OrderDirection.BUY, status=ExecutionStatus.FILLED, slippage=0.004,
            ))
            monitor.record(_make_record(
                direction=OrderDirection.SELL, status=ExecutionStatus.FILLED, slippage=0.004,
            ))
        assert monitor.check_health() == HealthStatus.WARNING

    def test_check_health_critical_high_slippage(self):
        monitor = ExecutionMonitor()
        for _ in range(5):
            monitor.record(_make_record(
                direction=OrderDirection.BUY, status=ExecutionStatus.FILLED, slippage=0.006,
            ))
            monitor.record(_make_record(
                direction=OrderDirection.SELL, status=ExecutionStatus.FILLED, slippage=0.006,
            ))
        assert monitor.check_health() == HealthStatus.CRITICAL

    def test_check_health_empty(self):
        monitor = ExecutionMonitor()
        assert monitor.check_health() == HealthStatus.HEALTHY

    def test_clear(self):
        monitor = ExecutionMonitor()
        monitor.record(_make_record())
        monitor.clear()
        assert monitor.get_stats().total_orders == 0
