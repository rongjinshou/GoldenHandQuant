from enum import StrEnum


class RebalanceFrequency(StrEnum):
    """再平衡频率枚举。"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
