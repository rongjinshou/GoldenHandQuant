import math
from src.domain.portfolio.interfaces.position_sizer import IPositionSizer
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.strategy.value_objects.signal import Signal
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position


class KellySizer(IPositionSizer):
    """凯利公式仓位计算器。

    公式: f* = (p * b - q) / b
    其中 p = 胜率, b = 盈亏比, q = 1 - p

    使用半凯利（half_kelly=True）以降低波动性。
    """

    def __init__(
        self,
        win_rate: float = 0.55,
        profit_loss_ratio: float = 1.5,
        half_kelly: bool = True,
        max_ratio: float = 0.25,
    ) -> None:
        self._win_rate = win_rate
        self._profit_loss_ratio = profit_loss_ratio
        self._use_half = half_kelly
        self._max_ratio = max_ratio

    def calculate_target(
        self, signal: Signal, price: float, asset: Asset, position: Position | None
    ) -> int:
        if asset is None or price <= 0:
            return 0

        p = self._win_rate
        b = self._profit_loss_ratio
        q = 1 - p

        if b <= 0:
            return 0
        kelly_fraction = (p * b - q) / b

        if self._use_half:
            kelly_fraction /= 2.0

        kelly_fraction = max(0.0, min(kelly_fraction, self._max_ratio))

        target_value = asset.total_asset * kelly_fraction
        target_volume = int(target_value / price)
        target_volume = (target_volume // 100) * 100  # A 股整手约束

        if signal.direction == OrderDirection.SELL and position is not None:
            target_volume = min(target_volume, position.available_volume)

        return target_volume
