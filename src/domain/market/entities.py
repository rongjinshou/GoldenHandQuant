from dataclasses import dataclass, field
from datetime import datetime

@dataclass(slots=True, kw_only=True)
class Bar:
    """行情 K 线实体。

    Attributes:
        symbol: 标的代码 (如 "600000.SH")。
        timestamp: K 线时间戳。
        open: 开盘价。
        high: 最高价。
        low: 最低价。
        close: 收盘价。
        volume: 成交量。
    """
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
