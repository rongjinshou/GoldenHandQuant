"""通知去重服务。

基于 (title, category, level) 的滑动窗口去重，相同事件在窗口期内只发送一次。
"""

from datetime import datetime, timedelta

from src.domain.notification.interfaces.repositories.notification_history_repository import (
    INotificationHistoryRepository,
)
from src.domain.notification.value_objects.notification_message import (
    NotificationMessage,
)


class NotificationDeduplicator:
    """通知去重器。

    通过查询通知历史仓储，在滑动窗口内检测重复消息。
    纯领域服务，不依赖任何第三方库。
    """

    def __init__(
        self,
        repository: INotificationHistoryRepository,
        window_seconds: int = 300,
    ) -> None:
        """
        Args:
            repository: 通知历史仓储。
            window_seconds: 去重窗口秒数，默认 300（5 分钟）。
        """
        self._repository = repository
        self._window_seconds = window_seconds

    def is_duplicate(self, message: NotificationMessage) -> bool:
        """判断消息是否为重复消息。

        在滑动窗口内是否存在相同 (title, category, level) 的记录。

        Args:
            message: 待检查的通知消息。

        Returns:
            True 表示重复，应跳过；False 表示不重复，可以发送。
        """
        since = datetime.now() - timedelta(seconds=self._window_seconds)
        existing = self._repository.find_recent_by_dedup_key(
            title=message.title,
            category=message.category,
            level=str(message.level),
            since=since,
        )
        return existing is not None

    @property
    def window_seconds(self) -> int:
        """去重窗口秒数。"""
        return self._window_seconds
