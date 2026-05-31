from dataclasses import dataclass
from datetime import datetime

from src.domain.strategy.value_objects.review_action import ReviewAction
from src.domain.strategy.value_objects.signal import Signal


@dataclass(slots=True, kw_only=True)
class SignalReviewRecord:
    """信号审核记录 — 一次审核决策的持久化快照。"""

    record_id: str
    signal: Signal
    action: ReviewAction
    reviewed_at: datetime
    reviewer_note: str = ""
    order_id: str = ""
    suggested_price: float = 0.0
    suggested_volume: int = 0
    risk_score: float = 0.0
    ml_confidence: float = 0.0
    signal_age_hours: float = 0.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.risk_score <= 1.0):
            raise ValueError(
                f"risk_score must be between 0.0 and 1.0, got {self.risk_score}"
            )
