from datetime import datetime

from src.domain.portfolio.services.rebalance_triggers.daily_trigger import DailyRebalanceTrigger


class TestDailyRebalanceTrigger:
    def test_first_time_always_triggers(self):
        trigger = DailyRebalanceTrigger()
        assert trigger.should_rebalance(datetime(2026, 1, 5), None) is True

    def test_same_day_does_not_trigger(self):
        trigger = DailyRebalanceTrigger()
        last = datetime(2026, 1, 5, 10, 0)
        assert trigger.should_rebalance(datetime(2026, 1, 5, 15, 0), last) is False

    def test_next_day_triggers(self):
        trigger = DailyRebalanceTrigger()
        last = datetime(2026, 1, 5)
        assert trigger.should_rebalance(datetime(2026, 1, 6), last) is True

    def test_multiple_days_later_triggers(self):
        trigger = DailyRebalanceTrigger()
        last = datetime(2026, 1, 1)
        assert trigger.should_rebalance(datetime(2026, 1, 10), last) is True

    def test_record_rebalance(self):
        trigger = DailyRebalanceTrigger()
        trigger.record_rebalance(datetime(2026, 1, 5))
        assert trigger._last_rebalance == datetime(2026, 1, 5)
