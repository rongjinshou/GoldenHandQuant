from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, kw_only=True)
class Quote:
    """实时行情快照（tick 级）。

    Attributes:
        symbol: 标的代码 (如 "601288.SH")。
        last: 最新价。
        bid1: 买一价（无买盘时为 None）。
        ask1: 卖一价（无卖盘时为 None）。
        prev_close: 前收盘价（涨跌停带基准）。
        timestamp: 行情时间。
    """
    symbol: str
    last: float
    bid1: float | None
    ask1: float | None
    prev_close: float
    timestamp: datetime
