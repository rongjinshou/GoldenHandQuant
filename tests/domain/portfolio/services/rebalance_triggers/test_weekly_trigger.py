from datetime import datetime

from src.domain.portfolio.services.rebalance_triggers.weekly_trigger import WeeklyRebalanceTrigger


class TestWeeklyRebalanceTrigger:
    def test_first_time_always_triggers(self):
        trigger = WeeklyRebalanceTrigger()
        assert trigger.should_rebalance(datetime(2026, 1, 5), None) is True

    def test_monday_after_5_days_triggers(self):
        # 2026-01-05 is Monday
        trigger = WeeklyRebalanceTrigger()
        last = datetime(2025, 12, 29)  # Monday
        assert trigger.should_rebalance(datetime(2026, 1, 5), last) is True

    def test_monday_less_than_5_days_no_trigger(self):
        # 2026-01-05 is Monday, last was Thursday 01-01
        trigger = WeeklyRebalanceTrigger()
        last = datetime(2026, 1, 1)  # Thursday
        assert trigger.should_rebalance(datetime(2026, 1, 5), last) is False

    def test_non_monday_no_trigger(self):
        # 2026-01-06 is Tuesday
        trigger = WeeklyRebalanceTrigger()
        last = datetime(2025, 12, 29)
        assert trigger.should_rebalance(datetime(2026, 1, 6), last) is False

    def test_record_rebalance(self):
        trigger = WeeklyRebalanceTrigger()
        trigger.record_rebalance(datetime(2026, 1, 5))
        assert trigger._last_rebalance == datetime(2026, 1, 5)
