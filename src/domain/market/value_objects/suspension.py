from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True, kw_only=True)
class StockStatus:
    """股票交易状态。"""
    symbol: str
    date: datetime
    is_suspended: bool = False     # 是否停牌
    is_st: bool = False            # 是否 ST (Special Treatment)
    is_star_st: bool = False       # 是否 *ST (退市风险警示)

    def is_tradable(self) -> bool:
        """是否可交易。"""
        return not self.is_suspended and not self.is_star_st


@dataclass(slots=True, kw_only=True)
class StockStatusRegistry:
    """股票状态注册表（内存索引）。

    维护一个日期→symbol→StockStatus 的稀疏索引。
    """
    _status: dict[str, dict[datetime, StockStatus]] = field(default_factory=dict)

    def add(self, status: StockStatus) -> None:
        date_key = status.date.replace(hour=0, minute=0, second=0, microsecond=0)
        if status.symbol not in self._status:
            self._status[status.symbol] = {}
        self._status[status.symbol][date_key] = status

    def is_tradable(self, symbol: str, date: datetime) -> bool:
        date_key = date.replace(hour=0, minute=0, second=0, microsecond=0)
        symbol_statuses = self._status.get(symbol, {})
        status = symbol_statuses.get(date_key)
        if status is None:
            return True  # 无记录默认可交易
        return status.is_tradable()

    def get_status(self, symbol: str, date: datetime) -> StockStatus | None:
        date_key = date.replace(hour=0, minute=0, second=0, microsecond=0)
        return self._status.get(symbol, {}).get(date_key)
