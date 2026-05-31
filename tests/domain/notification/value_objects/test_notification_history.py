"""通知历史值对象测试。"""

from datetime import datetime

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


def _make_message(level: NotificationLevel = NotificationLevel.INFO) -> NotificationMessage:
    return NotificationMessage(
        title="test",
        body="body",
        level=level,
        category="system",
    )


class TestNotificationHistory:
    """NotificationHistory 值对象测试。"""

    def test_create_without_receipt(self):
        msg = _make_message()
        history = NotificationHistory(
            notification_id="h1",
            message=msg,
            priority=NotificationPriority.INFO,
        )
        assert history.notification_id == "h1"
        assert history.delivered is False
        assert history.confirmed is False
        assert history.receipt is None

    def test_create_with_receipt(self):
        msg = _make_message()
        receipt = NotificationReceipt(
            notification_id="h1",
            sent_at=datetime.now(),
            delivered=True,
        )
        history = NotificationHistory(
            notification_id="h1",
            message=msg,
            priority=NotificationPriority.INFO,
            receipt=receipt,
            created_at=datetime.now(),
        )
        assert history.delivered is True
        assert history.confirmed is False

    def test_level_property(self):
        msg = _make_message(NotificationLevel.WARNING)
        history = NotificationHistory(
            notification_id="h1",
            message=msg,
            priority=NotificationPriority.WARNING,
        )
        assert history.level == NotificationLevel.WARNING

    def test_category_property(self):
        msg = _make_message()
        history = NotificationHistory(
            notification_id="h1",
            message=msg,
            priority=NotificationPriority.INFO,
        )
        assert history.category == "system"

    def test_frozen(self):
        msg = _make_message()
        history = NotificationHistory(
            notification_id="h1",
            message=msg,
            priority=NotificationPriority.INFO,
        )
        try:
            history.notification_id = "changed"  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass
