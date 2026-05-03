from abc import ABC, abstractmethod

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.strategy.value_objects.signal import Signal


class IPositionSizer(ABC):
    """仓位管理接口 (Position Sizer)。"""

    @abstractmethod
    def calculate_target(
        self,
        signal: Signal,
        current_price: float,
        asset: Asset,
        position: Position | None,
    ) -> float:
        """计算目标仓位。

        Returns:
            float: 目标数量（如股数）。
        """
        ...

    @abstractmethod
    def calculate_targets(
        self,
        signals: list[Signal],
        prices: dict[str, float],
        asset: Asset,
        positions: list[Position],
    ) -> list:
        """批量计算目标仓位。

        Args:
            signals: 策略 + 风控产出的全部信号列表。
            prices: symbol → 当前价格映射。
            asset: 账户资产。
            positions: 当前全部持仓。

        Returns:
            list[OrderTarget]: 包含调仓所需的全部 BUY 和 SELL 目标。
        """
        ...
