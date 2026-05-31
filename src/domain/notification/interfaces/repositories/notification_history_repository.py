"""通知历史仓储接口。"""

from datetime import datetime
from typing import Protocol

from src.domain.notification.value_objects.notification_history import (
    NotificationHistory,
)
from src.domain.notification.value_objects.notification_priority import (
    NotificationPriority,
)


class INotificationHistoryRepository(Protocol):
    """通知历史仓储接口。

    追踪所有已发送通知的记录，支持查询和统计。
    """

    def save(self, history: NotificationHistory) -> None:
        """保存一条通知历史记录。"""
        ...

    def find_by_id(self, notification_id: str) -> NotificationHistory | None:
        """根据 ID 查询通知历史。"""
        ...

    def query(
        self,
        *,
        category: str | None = None,
        priority: NotificationPriority | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[NotificationHistory]:
        """查询通知历史（支持多条件过滤，按时间倒序）。"""
        ...

    def find_recent_by_dedup_key(
        self,
        title: str,
        category: str,
        level: str,
        since: datetime,
    ) -> NotificationHistory | None:
        """根据去重键查找最近一条记录。

        用于滑动窗口去重：在 since 之后是否存在相同 (title, category, level) 的记录。
        """
        ...
