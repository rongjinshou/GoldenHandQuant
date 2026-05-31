"""算法订单配置值对象。"""

from dataclasses import dataclass

from src.domain.trade.value_objects.order_direction import OrderDirection


@dataclass(frozen=True, slots=True, kw_only=True)
class AlgoOrderConfig:
    """算法订单配置。

    Attributes:
        symbol: 证券代码。
        direction: 买卖方向。
        total_volume: 总委托数量。
        price_limit: 价格限制（限价单使用）。
        algo_type: 算法类型标识（twap/vwap/iceberg）。
        duration_minutes: 执行时长（分钟），TWAP/VWAP 使用。
        num_slices: 拆单数量，TWAP 使用。
        participation_rate: 参与率（0~1），VWAP 使用。
        display_volume: 每次显示数量，冰山单使用。
        strategy_name: 发起策略名称。
    """

    symbol: str
    direction: OrderDirection
    total_volume: int
    price_limit: float = 0.0
    algo_type: str = ""
    duration_minutes: int = 30
    num_slices: int = 5
    participation_rate: float = 0.1
    display_volume: int = 100
    strategy_name: str = ""

    def __post_init__(self) -> None:
        if self.total_volume <= 0:
            raise ValueError(f"Total volume must be positive, got {self.total_volume}")
        if self.price_limit < 0:
            raise ValueError(f"Price limit cannot be negative, got {self.price_limit}")
        if self.duration_minutes <= 0:
            raise ValueError(f"Duration must be positive, got {self.duration_minutes}")
        if self.num_slices <= 0:
            raise ValueError(f"Num slices must be positive, got {self.num_slices}")
        if not 0 < self.participation_rate <= 1:
            raise ValueError(
                f"Participation rate must be in (0, 1], got {self.participation_rate}"
            )
        if self.display_volume <= 0:
            raise ValueError(f"Display volume must be positive, got {self.display_volume}")
