from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, kw_only=True)
class FundamentalSnapshot:
    """单只股票在某交易日的基本面快照。

    Attributes:
        symbol: 标的代码 (如 "000001.SZ")。
        date: 交易日（ann_date，公告日期，非报告期）。
        name: 股票名称。
        list_date: 上市日期。
        market_cap: 总市值。
        roe_ttm: ROE (TTM)，可能缺失。
        ocf_ttm: 经营现金流净额 (TTM)，可能缺失。
    """
    symbol: str
    date: datetime
    name: str
    list_date: datetime
    market_cap: float
    roe_ttm: float | None = None
    ocf_ttm: float | None = None
