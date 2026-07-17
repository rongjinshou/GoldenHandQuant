from datetime import datetime

import pytest

from src.domain.strategy.pool.value_objects.performance_snapshot import PerformanceSnapshot
from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating


class TestPerformanceSnapshot:
    def _make_snapshot(self, **kwargs):
        defaults = dict(
            evaluated_at=datetime(2026, 1, 1),
            period_start=datetime(2025, 12, 1),
            period_end=datetime(2025, 12, 31),
            total_return=0.10,
            annualized_return=0.15,
            sharpe_ratio=1.5,
            max_drawdown=0.10,
            win_rate=0.60,
            trade_count=50,
            composite_score=75.0,
            rating=StrategyRating.B,
        )
        defaults.update(kwargs)
        return PerformanceSnapshot(**defaults)

    def test_creation(self):
        snap = self._make_snapshot()
        assert snap.rating == StrategyRating.B
        assert snap.composite_score == 75.0

    def test_immutability(self):
        snap = self._make_snapshot()
        with pytest.raises(AttributeError):
            snap.total_return = 0.20  # type: ignore[misc]

    def test_default_optional_fields(self):
        snap = self._make_snapshot()
        assert snap.benchmark_return == 0.0
        assert snap.underperform_weeks == 0
