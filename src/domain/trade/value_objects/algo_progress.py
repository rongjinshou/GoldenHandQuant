"""算法执行进度值对象。"""

from dataclasses import dataclass
from datetime import datetime

from src.domain.trade.value_objects.algo_order_status import AlgoOrderStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class AlgoProgress:
    """算法执行进度。

    Attributes:
        algo_id: 算法订单 ID。
        total_volume: 总目标数量。
        filled_volume: 已成交数量。
        remaining_volume: 剩余数量。
        avg_fill_price: 平均成交价。
        num_slices_total: 总子单数。
        num_slices_filled: 已成交子单数。
        status: 算法订单状态。
        started_at: 开始时间。
        completed_at: 完成时间。
    """

    algo_id: str
    total_volume: int
    filled_volume: int
    remaining_volume: int
    avg_fill_price: float = 0.0
    num_slices_total: int = 0
    num_slices_filled: int = 0
    status: AlgoOrderStatus = AlgoOrderStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def fill_ratio(self) -> float:
        """已成交比例。"""
        if self.total_volume == 0:
            return 0.0
        return self.filled_volume / self.total_volume
