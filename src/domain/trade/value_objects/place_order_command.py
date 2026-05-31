"""下单命令 DTO。

应用层通过 PlaceOrderCommand 向交易子域传递下单意图，
隔离接口层与领域层的直接耦合。
"""

from dataclasses import dataclass

from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaceOrderCommand:
    """下单命令。

    Attributes:
        symbol: 证券代码。
        direction: 买卖方向。
        volume: 委托数量。
        price: 委托价格。
        order_type: 订单类型（限价/市价）。
        strategy_name: 发出信号的策略名称。
    """

    symbol: str
    direction: OrderDirection
    volume: int
    price: float
    order_type: OrderType = OrderType.LIMIT
    strategy_name: str = ""

    def __post_init__(self) -> None:
        if self.volume <= 0:
            raise ValueError(f"Volume must be positive, got {self.volume}")
        if self.price < 0:
            raise ValueError(f"Price cannot be negative, got {self.price}")
