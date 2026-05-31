from enum import StrEnum


class ExecutionStatus(StrEnum):
    """执行状态枚举。"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELED = "canceled"
