from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.services.base_strategy import BaseStrategy
from src.domain.strategy.value_objects.signal import Signal


class CrossSectionalStrategy(BaseStrategy, ABC):
    """截面策略基类 — 操作全市场日频快照，产出批量信号。"""

    @abstractmethod
    def generate_cross_sectional_signals(
        self,
        universe: list[StockSnapshot],
        current_positions: list[Position],
        current_date: datetime,
    ) -> list[Signal]:
        ...

    def generate_signals(
        self,
        market_data: dict[str, list[Bar]],
        current_positions: list[Position],
    ) -> list[Signal]:
        raise NotImplementedError(
            "Use generate_cross_sectional_signals() for cross-sectional strategies"
        )
