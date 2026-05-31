from datetime import datetime

from src.application.notification_hub import NotificationHub, RateLimiter
from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)
from src.domain.trade.value_objects.execution_record import ExecutionRecord
from src.domain.trade.value_objects.execution_status import ExecutionStatus
from src.domain.trade.value_objects.execution_stats import ExecutionStats
from src.domain.trade.value_objects.order_direction import OrderDirection


class FakeGateway:
    """Fake INotificationGateway for testing."""
    def __init__(self) -> None:
        self.sent: list[NotificationMessage] = []
        self.fail_next: bool = False

    def send(self, message: NotificationMessage) -> bool:
        if self.fail_next:
            self.fail_next = False
            return False
        self.sent.append(message)
        return True

    def send_batch(self, messages: list[NotificationMessage]) -> int:
        count = 0
        for m in messages:
            if self.send(m):
                count += 1
        return count


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter(max_per_minute=3)
        assert limiter.allow()
        assert limiter.allow()
        assert limiter.allow()

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_per_minute=2)
        assert limiter.allow()
        assert limiter.allow()
        assert not limiter.allow()


class TestNotificationHub:
    def test_send_to_all_gateways(self):
        gw1 = FakeGateway()
        gw2 = FakeGateway()
        hub = NotificationHub([gw1, gw2], rate_limiter=RateLimiter(max_per_minute=100))

        msg = NotificationMessage(
            title="Test",
            body="Body",
            level=NotificationLevel.INFO,
            category="test",
        )
        hub.notify(msg)

        assert len(gw1.sent) == 1
        assert len(gw2.sent) == 1

    def test_rate_limit_blocks(self):
        gw = FakeGateway()
        hub = NotificationHub([gw], rate_limiter=RateLimiter(max_per_minute=2))

        msg = NotificationMessage(
            title="Test", body="Body",
            level=NotificationLevel.INFO, category="test",
        )
        hub.notify(msg)
        hub.notify(msg)
        hub.notify(msg)  # Should be blocked

        assert len(gw.sent) == 2

    def test_notify_trade_executed(self):
        gw = FakeGateway()
        hub = NotificationHub([gw], rate_limiter=RateLimiter(max_per_minute=100))

        record = ExecutionRecord(
            order_id="123",
            symbol="600000.SH",
            direction=OrderDirection.BUY,
            target_price=10.0,
            target_volume=100,
            status=ExecutionStatus.FILLED,
        )
        hub.notify_trade_executed(record)

        assert len(gw.sent) == 1
        assert "600000.SH" in gw.sent[0].title

    def test_notify_daily_report(self):
        gw = FakeGateway()
        hub = NotificationHub([gw], rate_limiter=RateLimiter(max_per_minute=100))

        stats = ExecutionStats(
            total_orders=10,
            successful_orders=9,
            failed_orders=1,
            success_rate=0.9,
            avg_slippage_buy=0.001,
            avg_slippage_sell=0.002,
            max_slippage=0.005,
            avg_fill_time_seconds=3.0,
        )
        hub.notify_daily_report(stats)

        assert len(gw.sent) == 1
        assert "执行报告" in gw.sent[0].title

    def test_gateway_failure_does_not_crash(self):
        gw = FakeGateway()
        gw.fail_next = True
        hub = NotificationHub([gw], rate_limiter=RateLimiter(max_per_minute=100))

        msg = NotificationMessage(
            title="Test", body="Body",
            level=NotificationLevel.INFO, category="test",
        )
        hub.notify(msg)  # Should not raise
        assert len(gw.sent) == 0
