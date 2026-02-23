from dataclasses import dataclass
from datetime import datetime

@dataclass(slots=True, kw_only=True)
class DailySnapshot:
    """每日账户快照实体。

    Attributes:
        date: 快照日期。
        total_asset: 当日总资产。
        available_cash: 当日可用资金。
        market_value: 持仓市值。
        pnl: 当日盈亏 (相对于昨日)。
        return_rate: 当日收益率。
    """
    date: datetime
    total_asset: float
    available_cash: float
    market_value: float
    pnl: float = 0.0
    return_rate: float = 0.0
