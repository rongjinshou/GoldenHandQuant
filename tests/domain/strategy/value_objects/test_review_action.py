from datetime import datetime

import pytest

from src.domain.strategy.value_objects.review_action import ReviewAction
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.strategy.value_objects.signal_review_record import SignalReviewRecord


class TestReviewAction:
    def test_values(self):
        assert ReviewAction.APPROVED == "approved"
        assert ReviewAction.REJECTED == "rejected"
        assert ReviewAction.SKIPPED == "skipped"

    def test_from_value(self):
        assert ReviewAction("approved") is ReviewAction.APPROVED


class TestSignalReviewRecord:
    def _make_record(self, risk_score: float = 0.2) -> SignalReviewRecord:
        signal = Signal(
            symbol="600000.SH",
            direction=SignalDirection.BUY,
            confidence_score=0.85,
            strategy_name="test",
            reason="test reason",
        )
        return SignalReviewRecord(
            record_id="abc123",
            signal=signal,
            action=ReviewAction.APPROVED,
            reviewed_at=datetime(2026, 5, 31, 9, 15, 0),
            risk_score=risk_score,
        )

    def test_create_valid(self):
        record = self._make_record()
        assert record.record_id == "abc123"
        assert record.signal.symbol == "600000.SH"
        assert record.action == ReviewAction.APPROVED
        assert record.risk_score == 0.2

    def test_risk_score_out_of_range_raises(self):
        with pytest.raises(ValueError, match="risk_score"):
            self._make_record(risk_score=1.5)

    def test_risk_score_negative_raises(self):
        with pytest.raises(ValueError, match="risk_score"):
            self._make_record(risk_score=-0.1)

    def test_default_values(self):
        record = self._make_record()
        assert record.reviewer_note == ""
        assert record.order_id == ""
        assert record.ml_confidence == 0.0
        assert record.signal_age_hours == 0.0
