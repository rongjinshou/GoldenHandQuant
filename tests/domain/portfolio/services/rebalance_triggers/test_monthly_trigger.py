from datetime import datetime

from src.domain.portfolio.services.rebalance_triggers.monthly_trigger import MonthlyRebalanceTrigger


class TestMonthlyRebalanceTrigger:
    def test_first_time_always_triggers(self):
        trigger = MonthlyRebalanceTrigger()
        assert trigger.should_rebalance(datetime(2026, 1, 1), None) is True

    def test_day_1_after_20_days_triggers(self):
        trigger = MonthlyRebalanceTrigger()
        last = datetime(2025, 12, 1)
        assert trigger.should_rebalance(datetime(2026, 1, 1), last) is True

    def test_day_2_after_20_days_triggers(self):
        trigger = MonthlyRebalanceTrigger()
        last = datetime(2025, 12, 10)
        assert trigger.should_rebalance(datetime(2026, 1, 2), last) is True

    def test_day_3_less_than_20_days_no_trigger(self):
        trigger = MonthlyRebalanceTrigger()
        last = datetime(2025, 12, 20)
        assert trigger.should_rebalance(datetime(2026, 1, 3), last) is False

    def test_day_4_no_trigger(self):
        trigger = MonthlyRebalanceTrigger()
        last = datetime(2025, 12, 1)
        assert trigger.should_rebalance(datetime(2026, 1, 4), last) is False

    def test_mid_month_no_trigger(self):
        trigger = MonthlyRebalanceTrigger()
        last = datetime(2025, 12, 1)
        assert trigger.should_rebalance(datetime(2026, 1, 15), last) is False

    def test_record_rebalance(self):
        trigger = MonthlyRebalanceTrigger()
        trigger.record_rebalance(datetime(2026, 1, 1))
        assert trigger._last_rebalance == datetime(2026, 1, 1)
