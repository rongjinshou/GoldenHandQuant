"""通知回执值对象测试。"""

from datetime import datetime

from src.domain.notification.value_objects.notification_receipt import (
    NotificationReceipt,
)


class TestNotificationReceipt:
    """NotificationReceipt 值对象测试。"""

    def test_create_with_defaults(self):
        receipt = NotificationReceipt(
            notification_id="abc123",
            sent_at=datetime(2026, 6, 1, 10, 0, 0),
        )
        assert receipt.notification_id == "abc123"
        assert receipt.sent_at == datetime(2026, 6, 1, 10, 0, 0)
        assert receipt.delivered is False
        assert receipt.confirmed is False
        assert receipt.confirmed_at is None

    def test_create_with_all_fields(self):
        sent = datetime(2026, 6, 1, 10, 0, 0)
        confirmed = datetime(2026, 6, 1, 10, 0, 5)
        receipt = NotificationReceipt(
            notification_id="abc123",
            sent_at=sent,
            delivered=True,
            confirmed=True,
            confirmed_at=confirmed,
        )
        assert receipt.delivered is True
        assert receipt.confirmed is True
        assert receipt.confirmed_at == confirmed

    def test_frozen(self):
        receipt = NotificationReceipt(
            notification_id="abc123",
            sent_at=datetime.now(),
        )
        try:
            receipt.delivered = True  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass

    def test_equality(self):
        now = datetime.now()
        r1 = NotificationReceipt(notification_id="x", sent_at=now)
        r2 = NotificationReceipt(notification_id="x", sent_at=now)
        assert r1 == r2
