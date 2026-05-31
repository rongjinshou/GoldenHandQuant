from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.domain.trade.value_objects.order_direction import OrderDirection


@dataclass(slots=True, kw_only=True)
class TradeRecord:
    """交易历史记录。"""

    order_id: str
    symbol: str
    direction: OrderDirection
    price: float
    volume: int
    strategy_name: str
    pnl: float = 0.0
    executed_at: datetime


class TradeHistoryRepository(Protocol):
    """交易历史仓储接口。"""

    def get_recent_trades(self, strategy_name: str, limit: int) -> list[TradeRecord]:
        """获取最近 N 笔交易。"""
        ...

    def get_trades_in_range(
        self, strategy_name: str, start: datetime, end: datetime,
    ) -> list[TradeRecord]:
        """获取指定时间范围内的交易。"""
        ...
