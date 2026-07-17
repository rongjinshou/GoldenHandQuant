"""TradingCalendar 测试（2026-07-10 六西格玛 M7）。"""

from datetime import date

from src.domain.trade.services.trading_calendar import TradingCalendar


def _calendar() -> TradingCalendar:
    # 2026-06 的一段真实形态: 周一~周五有 bar, 周末无, 6/10(周三)人为设为休市日
    days = [date(2026, 6, d) for d in (8, 9, 11, 12, 15, 16, 17, 18, 19)]
    return TradingCalendar.from_dates(days)


class TestTradingCalendar:
    def test_known_trading_day_is_true(self):
        assert _calendar().is_trading_day(date(2026, 6, 9)) is True

    def test_known_holiday_workday_is_false(self):
        """工作日休市(节假日) —— 时段闸旧逻辑只排周末, 这类日子曾放行。"""
        assert _calendar().is_trading_day(date(2026, 6, 10)) is False

    def test_weekend_is_false_within_known_range(self):
        assert _calendar().is_trading_day(date(2026, 6, 13)) is False  # 周六

    def test_future_date_is_unknown(self):
        assert _calendar().is_trading_day(date(2026, 6, 22)) is None

    def test_empty_dates_yield_no_calendar(self):
        assert TradingCalendar.from_dates([]) is None
