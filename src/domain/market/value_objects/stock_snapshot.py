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
    prev_close: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    return_20d: float | None = None       # 20 日收益率
    volatility_20d: float | None = None   # 20 日波动率
    turnover_rate: float | None = None    # 换手率
