"""通知优先级队列测试。"""

from src.domain.notification.services.notification_priority_queue import (
    NotificationPriorityQueue,
    SendAction,
)
from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)


def _make_message(level: NotificationLevel = NotificationLevel.INFO) -> NotificationMessage:
    return NotificationMessage(
        title="test",
        body="body",
        level=level,
        category="trade",
    )


class TestNotificationPriorityQueue:
    """NotificationPriorityQueue 测试。"""

    def test_emergency_sends_immediately(self):
        queue = NotificationPriorityQueue()
        msg = _make_message(NotificationLevel.EMERGENCY)
        result = queue.enqueue(msg)
        assert result.action == SendAction.SEND_IMMEDIATELY
        assert len(result.messages) == 1
        assert result.messages[0] is msg

    def test_critical_sends_immediately(self):
        queue = NotificationPriorityQueue()
        msg = _make_message(NotificationLevel.CRITICAL)
        result = queue.enqueue(msg)
        assert result.action == SendAction.SEND_IMMEDIATELY
        assert len(result.messages) == 1

    def test_warning_is_queued(self):
        queue = NotificationPriorityQueue()
        msg = _make_message(NotificationLevel.WARNING)
        result = queue.enqueue(msg)
        assert result.action == SendAction.QUEUED
        assert len(result.messages) == 0
        assert queue.pending_warning_count == 1

    def test_info_is_buffered(self):
        queue = NotificationPriorityQueue(batch_size=5)
        msg = _make_message(NotificationLevel.INFO)
        result = queue.enqueue(msg)
        assert result.action == SendAction.BUFFERED
        assert len(result.messages) == 0
        assert queue.buffered_info_count == 1

    def test_info_batch_triggers_at_threshold(self):
        queue = NotificationPriorityQueue(batch_size=3)
        for _ in range(2):
            result = queue.enqueue(_make_message(NotificationLevel.INFO))
            assert result.action == SendAction.BUFFERED

        result = queue.enqueue(_make_message(NotificationLevel.INFO))
        assert result.action == SendAction.SEND_BATCH
        assert len(result.messages) == 3
        assert queue.buffered_info_count == 0

    def test_flush_warnings(self):
        queue = NotificationPriorityQueue()
        queue.enqueue(_make_message(NotificationLevel.WARNING))
        queue.enqueue(_make_message(NotificationLevel.WARNING))
        assert queue.pending_warning_count == 2

        messages = queue.flush_warnings()
        assert len(messages) == 2
        assert queue.pending_warning_count == 0

    def test_flush_info_buffer(self):
        queue = NotificationPriorityQueue(batch_size=10)
        queue.enqueue(_make_message(NotificationLevel.INFO))
        queue.enqueue(_make_message(NotificationLevel.INFO))
        assert queue.buffered_info_count == 2

        messages = queue.flush_info_buffer()
        assert len(messages) == 2
        assert queue.buffered_info_count == 0

    def test_classify(self):
        assert NotificationPriorityQueue.classify(
            _make_message(NotificationLevel.EMERGENCY)
        ).value == "emergency"
        assert NotificationPriorityQueue.classify(
            _make_message(NotificationLevel.CRITICAL)
        ).value == "critical"
        assert NotificationPriorityQueue.classify(
            _make_message(NotificationLevel.WARNING)
        ).value == "warning"
        assert NotificationPriorityQueue.classify(
            _make_message(NotificationLevel.INFO)
        ).value == "info"

    def test_mixed_priority_flow(self):
        """模拟混合优先级的完整流程。"""
        queue = NotificationPriorityQueue(batch_size=2)

        # EMERGENCY -> 立即发送
        r1 = queue.enqueue(_make_message(NotificationLevel.EMERGENCY))
        assert r1.action == SendAction.SEND_IMMEDIATELY

        # WARNING -> 排队
        r2 = queue.enqueue(_make_message(NotificationLevel.WARNING))
        assert r2.action == SendAction.QUEUED

        # INFO x 2 -> 第二个触发批量
        r3 = queue.enqueue(_make_message(NotificationLevel.INFO))
        assert r3.action == SendAction.BUFFERED
        r4 = queue.enqueue(_make_message(NotificationLevel.INFO))
        assert r4.action == SendAction.SEND_BATCH
        assert len(r4.messages) == 2

        # flush warnings
        warnings = queue.flush_warnings()
        assert len(warnings) == 1
