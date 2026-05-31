"""NotificationHub 集成去重与优先级队列的扩展测试。"""

from datetime import datetime, timedelta

from src.application.notification_hub import NotificationHub, RateLimiter
from src.domain.notification.services.notification_deduplicator import (
    NotificationDeduplicator,
)
from src.domain.notification.services.notification_priority_queue import (
    NotificationPriorityQueue,
    SendAction,
)
from src.domain.notification.value_objects.notification_history import (
    NotificationHistory,
)
from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)
from src.domain.notification.value_objects.notification_priority import (
    NotificationPriority,
)
from src.domain.notification.value_objects.notification_receipt import (
    NotificationReceipt,
)


class FakeGateway:
    """伪造的通知网关。"""

    def __init__(self) -> None:
        self.sent: list[NotificationMessage] = []

    def send(self, message: NotificationMessage) -> bool:
        self.sent.append(message)
        return True

    def send_batch(self, messages: list[NotificationMessage]) -> int:
        self.sent.extend(messages)
        return len(messages)


class FakeHistoryRepository:
    """伪造的历史仓储。"""

    def __init__(self) -> None:
        self.records: list[NotificationHistory] = []

    def save(self, history: NotificationHistory) -> None:
        self.records.append(history)

    def find_recent_by_dedup_key(
        self,
        title: str,
        category: str,
        level: str,
        since: datetime,
    ) -> NotificationHistory | None:
        for record in reversed(self.records):
            if (
                record.message.title == title
                and record.message.category == category
                and str(record.message.level) == level
                and record.created_at is not None
                and record.created_at >= since
            ):
                return record
        return None


def _make_message(
    level: NotificationLevel = NotificationLevel.INFO,
    title: str = "test",
) -> NotificationMessage:
    return NotificationMessage(
        title=title,
        body="body",
        level=level,
        category="trade",
    )


class TestNotificationHubWithDedup:
    """NotificationHub 去重集成测试。"""

    def test_duplicate_message_is_skipped(self):
        gateway = FakeGateway()
        repo = FakeHistoryRepository()
        dedup = NotificationDeduplicator(repo, window_seconds=300)
        hub = NotificationHub(
            gateways=[gateway],
            deduplicator=dedup,
            rate_limiter=RateLimiter(max_per_minute=100),
        )

        # 第一次发送
        hub.notify(_make_message(title="alert"))
        assert len(gateway.sent) == 1

        # 模拟历史记录（刚发送的）
        repo.records.append(
            NotificationHistory(
                notification_id="1",
                message=_make_message(title="alert"),
                priority=NotificationPriority.INFO,
                created_at=datetime.now() - timedelta(seconds=10),
            )
        )

        # 第二次相同消息应被去重
        hub.notify(_make_message(title="alert"))
        assert len(gateway.sent) == 1  # 仍然只有 1 条

    def test_different_messages_not_deduplicated(self):
        gateway = FakeGateway()
        repo = FakeHistoryRepository()
        dedup = NotificationDeduplicator(repo, window_seconds=300)
        hub = NotificationHub(
            gateways=[gateway],
            deduplicator=dedup,
            rate_limiter=RateLimiter(max_per_minute=100),
        )

        hub.notify(_make_message(title="alert-a"))
        repo.records.append(
            NotificationHistory(
                notification_id="1",
                message=_make_message(title="alert-a"),
                priority=NotificationPriority.INFO,
                created_at=datetime.now(),
            )
        )

        hub.notify(_make_message(title="alert-b"))
        assert len(gateway.sent) == 2


class TestNotificationHubWithPriorityQueue:
    """NotificationHub 优先级队列集成测试。"""

    def test_emergency_bypasses_queue(self):
        gateway = FakeGateway()
        pq = NotificationPriorityQueue()
        hub = NotificationHub(
            gateways=[gateway],
            priority_queue=pq,
            rate_limiter=RateLimiter(max_per_minute=100),
        )

        hub.notify(_make_message(NotificationLevel.EMERGENCY))
        assert len(gateway.sent) == 1

    def test_critical_bypasses_queue(self):
        gateway = FakeGateway()
        pq = NotificationPriorityQueue()
        hub = NotificationHub(
            gateways=[gateway],
            priority_queue=pq,
            rate_limiter=RateLimiter(max_per_minute=100),
        )

        hub.notify(_make_message(NotificationLevel.CRITICAL))
        assert len(gateway.sent) == 1

    def test_warning_queued_not_sent_immediately(self):
        gateway = FakeGateway()
        pq = NotificationPriorityQueue()
        hub = NotificationHub(
            gateways=[gateway],
            priority_queue=pq,
            rate_limiter=RateLimiter(max_per_minute=100),
        )

        hub.notify(_make_message(NotificationLevel.WARNING))
        assert len(gateway.sent) == 0
        assert pq.pending_warning_count == 1

    def test_info_buffered_not_sent_immediately(self):
        gateway = FakeGateway()
        pq = NotificationPriorityQueue(batch_size=10)
        hub = NotificationHub(
            gateways=[gateway],
            priority_queue=pq,
            rate_limiter=RateLimiter(max_per_minute=100),
        )

        hub.notify(_make_message(NotificationLevel.INFO))
        assert len(gateway.sent) == 0
        assert pq.buffered_info_count == 1

    def test_info_batch_sent_when_threshold_reached(self):
        gateway = FakeGateway()
        pq = NotificationPriorityQueue(batch_size=2)
        hub = NotificationHub(
            gateways=[gateway],
            priority_queue=pq,
            rate_limiter=RateLimiter(max_per_minute=100),
        )

        hub.notify(_make_message(NotificationLevel.INFO))
        assert len(gateway.sent) == 0
        hub.notify(_make_message(NotificationLevel.INFO))
        assert len(gateway.sent) == 2  # 批量发送

    def test_flush_sends_queued_messages(self):
        gateway = FakeGateway()
        pq = NotificationPriorityQueue(batch_size=10)
        hub = NotificationHub(
            gateways=[gateway],
            priority_queue=pq,
            rate_limiter=RateLimiter(max_per_minute=100),
        )

        hub.notify(_make_message(NotificationLevel.WARNING))
        hub.notify(_make_message(NotificationLevel.INFO))
        assert len(gateway.sent) == 0

        hub.flush()
        assert len(gateway.sent) == 2


class TestNotificationHubWithHistory:
    """NotificationHub 历史记录集成测试。"""

    def test_history_recorded_on_send(self):
        gateway = FakeGateway()
        repo = FakeHistoryRepository()
        hub = NotificationHub(
            gateways=[gateway],
            history_repository=repo,
            rate_limiter=RateLimiter(max_per_minute=100),
        )

        hub.notify(_make_message(NotificationLevel.INFO))
        assert len(gateway.sent) == 1
        assert len(repo.records) == 1
        assert repo.records[0].delivered is True
        assert repo.records[0].priority == NotificationPriority.INFO


class TestNotificationHubWithoutOptionalDeps:
    """不传入可选依赖时的兼容性测试。"""

    def test_basic_notify_without_dedup_queue_history(self):
        gateway = FakeGateway()
        hub = NotificationHub(
            gateways=[gateway],
            rate_limiter=RateLimiter(max_per_minute=100),
        )

        hub.notify(_make_message(NotificationLevel.INFO))
        assert len(gateway.sent) == 1

    def test_flush_noop_without_queue(self):
        gateway = FakeGateway()
        hub = NotificationHub(
            gateways=[gateway],
            rate_limiter=RateLimiter(max_per_minute=100),
        )
        # 不应抛异常
        hub.flush()
