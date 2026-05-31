from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class NotificationLevel(StrEnum):
    """通知级别。"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass(slots=True, kw_only=True)
class NotificationMessage:
    """通知消息值对象。"""

    title: str
    body: str
    level: NotificationLevel
    category: str  # trade / risk / anomaly / system
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, str] = field(default_factory=dict)
