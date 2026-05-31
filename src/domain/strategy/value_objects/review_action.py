from enum import StrEnum


class ReviewAction(StrEnum):
    """信号审核动作。"""
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"
