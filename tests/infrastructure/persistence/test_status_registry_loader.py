"""区间 → StockStatusRegistry 稠密展开(设计 0711-st-honesty §4.1)。"""
from datetime import date, datetime

from src.infrastructure.gateway.st_status_source import StPeriod
from src.infrastructure.persistence.status_registry_loader import build_status_registry


class FakeStore:
    def __init__(self, periods, tds):
        self._periods = periods
        self._tds = tds

    def load_st_periods(self):
        return self._periods

    def trading_dates(self, source="qmt"):
        return self._tds


TDS = [date(2022, 5, 5), date(2022, 5, 6), date(2022, 5, 9), date(2022, 5, 10)]


def test_expand_closed_interval_on_trading_days_only():
    periods = [StPeriod(symbol="000021.SZ", start=date(2022, 5, 6), end=date(2022, 5, 10),
                        label="ST", source="szse_name_change", evidence="")]
    reg = build_status_registry(FakeStore(periods, TDS),
                                start=date(2022, 5, 1), end=date(2022, 5, 31))
    assert reg.get_status("000021.SZ", datetime(2022, 5, 6)).is_st is True
    assert reg.get_status("000021.SZ", datetime(2022, 5, 9)).is_st is True
    assert reg.get_status("000021.SZ", datetime(2022, 5, 10)) is None   # end 不含
    assert reg.get_status("000021.SZ", datetime(2022, 5, 7)) is None    # 非交易日不展开
    assert reg.get_status("000021.SZ", datetime(2022, 5, 5)) is None


def test_open_interval_and_star_label_and_window_clip():
    periods = [StPeriod(symbol="600696.SH", start=date.min, end=None,
                        label="*ST", source="cninfo_notice", evidence="")]
    reg = build_status_registry(FakeStore(periods, TDS),
                                start=date(2022, 5, 6), end=date(2022, 5, 9))
    s = reg.get_status("600696.SH", datetime(2022, 5, 9))
    assert s is not None and s.is_star_st is True and s.is_st is False
    assert reg.get_status("600696.SH", datetime(2022, 5, 5)) is None    # 窗口裁剪
    assert reg.get_status("600696.SH", datetime(2022, 5, 10)) is None


def test_empty_table_returns_none():
    assert build_status_registry(FakeStore([], TDS),
                                 start=date(2022, 1, 1), end=date(2022, 12, 31)) is None
