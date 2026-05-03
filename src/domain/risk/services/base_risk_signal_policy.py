from abc import ABC, abstractmethod

from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.strategy.value_objects.signal import Signal


class BaseRiskSignalPolicy(ABC):
    """盘后风控信号策略 — 主动产出 SELL 信号，而非拦截订单。"""

    @abstractmethod
    def evaluate_positions(
        self, positions: list[Position], bars: dict[str, Bar]
    ) -> list[Signal]:
        ...
