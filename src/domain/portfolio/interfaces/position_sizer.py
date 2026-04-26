from abc import ABC, abstractmethod
from src.domain.strategy.value_objects.signal import Signal
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position

class IPositionSizer(ABC):
    """仓位管理接口 (Position Sizer)。"""

    @abstractmethod
    def calculate_target(
        self, 
        signal: Signal, 
        current_price: float, 
        asset: Asset, 
        position: Position | None
    ) -> int:
        """根据信号计算目标交易量。

        Args:
            signal: 交易信号。
            current_price: 当前价格。
            asset: 账户资产信息。
            position: 当前持仓信息 (可能为 None)。

        Returns:
            int: 目标交易数量。
        """
        pass
