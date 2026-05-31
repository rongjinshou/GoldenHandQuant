from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class PositionDetail:
    """持仓明细 — 包含实时盈亏计算。"""

    ticker: str
    total_volume: int
    available_volume: int
    average_cost: float
    current_price: float

    @property
    def market_value(self) -> float:
        return self.total_volume * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.average_cost) * self.total_volume

    @property
    def pnl_ratio(self) -> float:
        if self.average_cost <= 0:
            return 0.0
        return (self.current_price - self.average_cost) / self.average_cost
