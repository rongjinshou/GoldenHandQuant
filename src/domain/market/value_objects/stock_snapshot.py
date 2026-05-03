from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, kw_only=True)
class StockSnapshot:
    """Bar + FundamentalSnapshot 合并视图，过滤器的标准输入。"""
    symbol: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    name: str
    list_date: datetime
    market_cap: float
    roe_ttm: float | None = None
    ocf_ttm: float | None = None
