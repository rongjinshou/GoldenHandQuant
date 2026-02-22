from abc import ABC, abstractmethod

from src.domain.account.position import Position
from src.domain.market.entities import Bar
from src.domain.strategy.entities import Signal


class BaseStrategy(ABC):
    """策略抽象基类。

    所有具体策略实现必须继承此类，并实现 `generate_signals` 方法。
    策略应保持无状态或最小状态，仅作为纯逻辑计算模块。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称。"""
        pass

    @abstractmethod
    def generate_signals(
        self,
        market_data: dict[str, list[Bar]],
        current_positions: list[Position],
    ) -> list[Signal]:
        """根据行情数据和持仓生成交易信号。

        Args:
            market_data: 市场行情数据，键为 symbol，值为 Bar 列表。
            current_positions: 当前持仓列表。

        Returns:
            生成的信号列表 (list[Signal])。
        """
        pass
