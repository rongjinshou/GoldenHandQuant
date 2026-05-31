"""通知优先级枚举。"""

from enum import StrEnum


class NotificationPriority(StrEnum):
    """通知优先级。

    决定通知的发送策略：
    - EMERGENCY: 立即发送，忽略频率限制和静默时段
    - CRITICAL: 立即发送，忽略静默时段
    - WARNING: 进入队列，按序发送
    - INFO: 批量合并后发送
    """

    EMERGENCY = "emergency"
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
