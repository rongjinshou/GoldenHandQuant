from enum import StrEnum


class AlgoOrderStatus(StrEnum):
    """算法订单状态枚举。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"
