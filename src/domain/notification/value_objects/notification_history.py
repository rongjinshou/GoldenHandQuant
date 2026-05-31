"""通知历史值对象。"""

from dataclasses import dataclass
from datetime import datetime

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


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationHistory:
    """通知历史记录，关联消息、优先级与回执。"""

    notification_id: str
    message: NotificationMessage
    priority: NotificationPriority
    receipt: NotificationReceipt | None = None
    created_at: datetime | None = None

    @property
    def level(self) -> NotificationLevel:
        return self.message.level

    @property
    def category(self) -> str:
        return self.message.category

    @property
    def delivered(self) -> bool:
        return self.receipt.delivered if self.receipt else False

    @property
    def confirmed(self) -> bool:
        return self.receipt.confirmed if self.receipt else False
