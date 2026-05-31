"""通知回执值对象。"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationReceipt:
    """通知回执，记录通知的投递与确认状态。"""

    notification_id: str
    sent_at: datetime
    delivered: bool = False
    confirmed: bool = False
    confirmed_at: datetime | None = None
