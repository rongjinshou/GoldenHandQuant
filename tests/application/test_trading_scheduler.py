"""TradingScheduler 测试。"""

from datetime import datetime

from src.application.trading_scheduler import TradingScheduler


class TestTradingScheduler:
    def test_is_running_false_by_default(self):
        scheduler = TradingScheduler()
        assert not scheduler.is_running

    def test_is_trading_hour_morning_session(self):
        scheduler = TradingScheduler()
        assert scheduler._is_trading_hour(datetime(2025, 1, 1, 10, 0))

    def test_is_trading_hour_afternoon_session(self):
        scheduler = TradingScheduler()
        assert scheduler._is_trading_hour(datetime(2025, 1, 1, 14, 0))

    def test_is_not_trading_hour_before_open(self):
        scheduler = TradingScheduler()
        assert not scheduler._is_trading_hour(datetime(2025, 1, 1, 8, 0))

    def test_is_not_trading_hour_after_close(self):
        scheduler = TradingScheduler()
        assert not scheduler._is_trading_hour(datetime(2025, 1, 1, 16, 0))

    def test_is_not_trading_hour_lunch_break(self):
        scheduler = TradingScheduler()
        assert not scheduler._is_trading_hour(datetime(2025, 1, 1, 12, 0))

    def test_should_execute_matching_time(self):
        scheduler = TradingScheduler(execution_times=["09:35", "14:50"])
        assert scheduler._should_execute(datetime(2025, 1, 1, 9, 35))

    def test_should_not_execute_non_matching_time(self):
        scheduler = TradingScheduler(execution_times=["09:35"])
        assert not scheduler._should_execute(datetime(2025, 1, 1, 9, 36))

    def test_register_callback(self):
        scheduler = TradingScheduler()
        called_with = []

        def on_cycle(now):
            called_with.append(now)

        scheduler.register_cycle_callback(on_cycle)
        assert scheduler._on_cycle is on_cycle

    def test_start_without_callback_raises(self):
        scheduler = TradingScheduler()
        try:
            scheduler.start()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "未注册" in str(e)
