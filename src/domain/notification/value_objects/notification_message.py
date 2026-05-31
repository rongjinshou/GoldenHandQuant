import copy
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class NotificationLevel(StrEnum):
    """通知级别。"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass(frozen=True, slots=True, kw_only=True)
class NotificationMessage:
    """通知消息值对象。"""

    title: str
    body: str
    level: NotificationLevel
    category: str  # trade / risk / anomaly / system
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        for field_name in self.__dataclass_fields__:
            val = getattr(self, field_name)
            if isinstance(val, (list, dict, set)):
                object.__setattr__(self, field_name, copy.deepcopy(val))
