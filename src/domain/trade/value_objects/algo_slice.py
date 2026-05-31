"""算法子单值对象。"""

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_status import OrderStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class AlgoSlice:
    """算法拆分后的子单。

    Attributes:
        slice_id: 子单 ID。
        parent_algo_id: 父算法订单 ID。
        symbol: 证券代码。
        direction: 买卖方向。
        price: 委托价格。
        volume: 委托数量。
        order_id: 实际下单后返回的订单 ID。
        status: 子单状态。
        scheduled_at: 计划执行时间。
        executed_at: 实际执行时间。
    """

    slice_id: str
    parent_algo_id: str
    symbol: str
    direction: OrderDirection
    price: float
    volume: int
    order_id: str = ""
    status: OrderStatus = OrderStatus.CREATED
    scheduled_at: datetime = field(default_factory=datetime.now)
    executed_at: datetime | None = None
