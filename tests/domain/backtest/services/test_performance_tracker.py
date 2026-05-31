from datetime import datetime

import pytest

from src.domain.backtest.services.performance_tracker import PerformanceTracker


class TestPerformanceTracker:
    def test_record_and_get_performance(self):
        tracker = PerformanceTracker(lookback_days=60)
        base = datetime(2026, 1, 1)
        for i in range(30):
            tracker.record_daily_return("strategy_A", 0.001 * (i % 3 - 1), base.replace(day=1 + i))

        perf = tracker.get_performance("strategy_A")
        assert perf is not None
        assert perf.strategy_name == "strategy_A"
        assert perf.lookback_days == 30

    def test_insufficient_data_returns_none(self):
        tracker = PerformanceTracker(lookback_days=60)
        tracker.record_daily_return("A", 0.01, datetime(2026, 1, 1))
        assert tracker.get_performance("A") is None

    def test_nonexistent_strategy_returns_none(self):
        tracker = PerformanceTracker()
        assert tracker.get_performance("nonexistent") is None

    def test_get_all_performances(self):
        tracker = PerformanceTracker(lookback_days=10)
        base = datetime(2026, 1, 1)
        for i in range(15):
            tracker.record_daily_return("A", 0.01, base.replace(day=1 + i))
            tracker.record_daily_return("B", -0.005, base.replace(day=1 + i))

        perfs = tracker.get_all_performances()
        names = {p.strategy_name for p in perfs}
        assert "A" in names
        assert "B" in names

    def test_window_trimming(self):
        tracker = PerformanceTracker(lookback_days=10)
        base = datetime(2026, 1, 1)
        # Record 30 days of data (more than lookback * 2 = 20)
        for i in range(30):
            tracker.record_daily_return("A", 0.01, base.replace(day=1 + i))

        # Internal storage should be trimmed
        assert len(tracker._returns["A"]) <= 20

    def test_positive_return_strategy(self):
        tracker = PerformanceTracker(lookback_days=60)
        base = datetime(2026, 1, 1)
        for i in range(30):
            tracker.record_daily_return("winner", 0.005, base.replace(day=1 + i))

        perf = tracker.get_performance("winner")
        assert perf is not None
        assert perf.total_return > 0
        assert perf.win_rate == 1.0

    def test_negative_return_strategy(self):
        tracker = PerformanceTracker(lookback_days=60)
        base = datetime(2026, 1, 1)
        for i in range(30):
            tracker.record_daily_return("loser", -0.005, base.replace(day=1 + i))

        perf = tracker.get_performance("loser")
        assert perf is not None
        assert perf.total_return < 0
        assert perf.win_rate == 0.0

    def test_mixed_returns(self):
        tracker = PerformanceTracker(lookback_days=60)
        base = datetime(2026, 1, 1)
        returns = [0.01, -0.005, 0.02, -0.01, 0.005, 0.015, -0.008, 0.003, -0.002, 0.01]
        for i, r in enumerate(returns):
            tracker.record_daily_return("mixed", r, base.replace(day=1 + i))

        perf = tracker.get_performance("mixed")
        assert perf is not None
        assert 0 < perf.win_rate < 1.0
        assert perf.volatility > 0
        assert perf.profit_loss_ratio > 0
