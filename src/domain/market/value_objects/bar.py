from dataclasses import dataclass
from datetime import datetime
from src.domain.market.value_objects.timeframe import Timeframe

@dataclass(slots=True, kw_only=True)
class Bar:
    """行情 K 线实体。

    Attributes:
        symbol: 标的代码 (如 "600000.SH")。
        timeframe: K 线周期。
        timestamp: K 线时间戳。
        open: 开盘价 (前复权)。
        high: 最高价 (前复权)。
        low: 最低价 (前复权)。
        close: 收盘价 (前复权)。
        volume: 成交量。
        unadjusted_close: 不复权收盘价，用于真实账本结算。
    """
    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    unadjusted_close: float = 0.0
