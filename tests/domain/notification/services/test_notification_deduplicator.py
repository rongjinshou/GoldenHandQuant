"""通知去重服务测试。"""

from datetime import datetime, timedelta

from src.domain.notification.services.notification_deduplicator import (
    NotificationDeduplicator,
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


class FakeHistoryRepository:
    """伪造的历史仓储，用于测试去重逻辑。"""

    def __init__(self) -> None:
        self.records: list[NotificationHistory] = []

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

    def save(self, history: NotificationHistory) -> None:
        self.records.append(history)


def _make_message(
    title: str = "test",
    category: str = "trade",
    level: NotificationLevel = NotificationLevel.INFO,
) -> NotificationMessage:
    return NotificationMessage(title=title, body="body", level=level, category=category)


class TestNotificationDeduplicator:
    """NotificationDeduplicator 测试。"""

    def test_not_duplicate_when_no_history(self):
        repo = FakeHistoryRepository()
        dedup = NotificationDeduplicator(repo, window_seconds=300)
        msg = _make_message()
        assert dedup.is_duplicate(msg) is False

    def test_duplicate_within_window(self):
        repo = FakeHistoryRepository()
        msg = _make_message()
        repo.records.append(
            NotificationHistory(
                notification_id="1",
                message=msg,
                priority=NotificationPriority.INFO,
                created_at=datetime.now() - timedelta(seconds=60),
            )
        )
        dedup = NotificationDeduplicator(repo, window_seconds=300)
        assert dedup.is_duplicate(msg) is True

    def test_not_duplicate_outside_window(self):
        repo = FakeHistoryRepository()
        msg = _make_message()
        repo.records.append(
            NotificationHistory(
                notification_id="1",
                message=msg,
                priority=NotificationPriority.INFO,
                created_at=datetime.now() - timedelta(seconds=400),
            )
        )
        dedup = NotificationDeduplicator(repo, window_seconds=300)
        assert dedup.is_duplicate(msg) is False

    def test_different_title_not_duplicate(self):
        repo = FakeHistoryRepository()
        repo.records.append(
            NotificationHistory(
                notification_id="1",
                message=_make_message(title="title-a"),
                priority=NotificationPriority.INFO,
                created_at=datetime.now() - timedelta(seconds=60),
            )
        )
        dedup = NotificationDeduplicator(repo, window_seconds=300)
        assert dedup.is_duplicate(_make_message(title="title-b")) is False

    def test_different_category_not_duplicate(self):
        repo = FakeHistoryRepository()
        repo.records.append(
            NotificationHistory(
                notification_id="1",
                message=_make_message(category="trade"),
                priority=NotificationPriority.INFO,
                created_at=datetime.now() - timedelta(seconds=60),
            )
        )
        dedup = NotificationDeduplicator(repo, window_seconds=300)
        assert dedup.is_duplicate(_make_message(category="risk")) is False

    def test_different_level_not_duplicate(self):
        repo = FakeHistoryRepository()
        repo.records.append(
            NotificationHistory(
                notification_id="1",
                message=_make_message(level=NotificationLevel.INFO),
                priority=NotificationPriority.INFO,
                created_at=datetime.now() - timedelta(seconds=60),
            )
        )
        dedup = NotificationDeduplicator(repo, window_seconds=300)
        assert dedup.is_duplicate(_make_message(level=NotificationLevel.WARNING)) is False

    def test_default_window_is_5_minutes(self):
        repo = FakeHistoryRepository()
        dedup = NotificationDeduplicator(repo)
        assert dedup.window_seconds == 300
