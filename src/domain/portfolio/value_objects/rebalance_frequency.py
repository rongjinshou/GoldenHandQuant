from enum import Enum


class RebalanceFrequency(Enum):
    """再平衡频率枚举。"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
