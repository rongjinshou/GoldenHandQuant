from datetime import datetime

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.backtest.value_objects.bar_window import BarWindow, make_bar_window


def _bar(dt: datetime, open_: float, close: float) -> Bar:
    return Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=dt,
               open=open_, high=close * 1.02, low=open_ * 0.98, close=close, volume=1e6)


def test_make_bar_window_splits_info_and_exec():
    recent = [
        _bar(datetime(2024, 6, 1), 9.0, 9.5),
        _bar(datetime(2024, 6, 2), 9.5, 10.0),
        _bar(datetime(2024, 6, 3), 10.0, 12.0),  # 成交 bar(T 日)
    ]
    window = make_bar_window(recent)
    assert window is not None
    assert len(window.info_bars) == 2
    assert window.info_bars[-1].timestamp == datetime(2024, 6, 2)   # 信息止于 T-1
    assert window.exec_bar.timestamp == datetime(2024, 6, 3)        # 成交 bar 是 T 日
    assert window.exec_price == 10.0   # 成交价 = T 日开盘
    assert window.mark_price == 12.0   # 估值价 = T 日收盘


def test_make_bar_window_returns_none_when_too_few_bars():
    assert make_bar_window([]) is None
    assert make_bar_window([_bar(datetime(2024, 6, 3), 10.0, 12.0)]) is None
