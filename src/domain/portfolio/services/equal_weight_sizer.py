from src.domain.portfolio.interfaces.position_sizer import IPositionSizer
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.strategy.value_objects.signal import Signal
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position


class EqualWeightSizer(IPositionSizer):
    """等权重仓位再平衡器。

    将总资金均分给 N 个标的，每个标的目标市值 = total_asset / n_symbols。
    根据当前持仓偏离度生成买入/卖出信号以达到等权重。
    """

    def __init__(self, n_symbols: int, rebalance_threshold: float = 0.05) -> None:
        self._n_symbols = n_symbols
        self._threshold = rebalance_threshold

    def calculate_target(
        self, signal: Signal, price: float, asset: Asset, position: Position | None
    ) -> int:
        if asset is None or price <= 0 or self._n_symbols <= 0:
            return 0

        target_value_per_symbol = asset.total_asset / self._n_symbols
        current_value = (position.total_volume * price) if position else 0.0
        deviation = (current_value - target_value_per_symbol) / target_value_per_symbol

        if abs(deviation) < self._threshold:
            return 0

        target_volume = int((target_value_per_symbol - current_value) / price)
        target_volume = (target_volume // 100) * 100

        if target_volume > 0 and signal.direction == OrderDirection.SELL:
            target_volume = 0
        elif target_volume < 0 and signal.direction == OrderDirection.BUY:
            target_volume = 0

        if target_volume < 0 and position is not None:
            target_volume = max(target_volume, -position.available_volume)

        return abs(target_volume) if target_volume > 0 else 0
