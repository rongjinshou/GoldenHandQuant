from enum import StrEnum


class StrategyStatus(StrEnum):
    """策略生命周期状态。"""

    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"
