from dataclasses import dataclass, field
from datetime import datetime

from src.domain.trade.value_objects.execution_status import ExecutionStatus
from src.domain.trade.value_objects.order_direction import OrderDirection


@dataclass(slots=True, kw_only=True)
class ExecutionRecord:
    """执行记录值对象。

    记录一次订单从提交到成交/失败的完整生命周期。
    """

    order_id: str
    symbol: str
    direction: OrderDirection
    target_price: float
    target_volume: int
    actual_price: float | None = None
    actual_volume: int = 0
    slippage: float = 0.0
    status: ExecutionStatus = ExecutionStatus.PENDING
    error_message: str = ""
    strategy_name: str = ""
    submitted_at: datetime = field(default_factory=datetime.now)
    filled_at: datetime | None = None
