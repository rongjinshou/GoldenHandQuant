"""VWAP (Volume-Weighted Average Price) 算法策略。

根据历史成交量分布拆单，在成交量高的时段分配更多数量，
使成交均价趋近于成交量加权平均价格。
"""

from datetime import datetime, timedelta
from uuid import uuid4

from src.domain.trade.value_objects.algo_order_config import AlgoOrderConfig
from src.domain.trade.value_objects.algo_slice import AlgoSlice
from src.domain.trade.value_objects.order_direction import OrderDirection


class VwapStrategy:
    """VWAP 策略：成交量加权平均价格算法。

    根据每个时间段的历史成交量占比来分配子单数量，
    高成交量时段分配更多数量，低成交量时段分配更少。
    """

    def generate_slices(
        self,
        config: AlgoOrderConfig,
        parent_algo_id: str,
        volume_profile: list[float] | None = None,
        start_time: datetime | None = None,
    ) -> list[AlgoSlice]:
        """生成 VWAP 子单列表。

        Args:
            config: 算法订单配置。
            parent_algo_id: 父算法订单 ID。
            volume_profile: 各时间段的历史成交量占比列表，
                           长度应与 num_slices 一致，元素之和应为 1.0。
                           若为 None，则退化为均匀分配。
            start_time: 开始时间，默认为当前时间。

        Returns:
            拆分后的子单列表。
        """
        now = start_time or datetime.now()
        num_slices = config.num_slices

        # 无成交量分布时退化为均匀分配
        if volume_profile is None:
            volume_profile = [1.0 / num_slices] * num_slices

        # 归一化，确保总和为 1.0
        total_ratio = sum(volume_profile)
        if total_ratio <= 0:
            volume_profile = [1.0 / num_slices] * num_slices
            total_ratio = 1.0
        normalized = [r / total_ratio for r in volume_profile]

        interval = timedelta(minutes=config.duration_minutes / num_slices)
        slices: list[AlgoSlice] = []
        allocated_total = 0

        for i in range(num_slices):
            if i == num_slices - 1:
                # 最后一个子单接收全部剩余，避免舍入误差
                vol = config.total_volume - allocated_total
            else:
                vol = int(config.total_volume * normalized[i])
                vol = self._round_volume(vol, config.direction)

            allocated_total += vol

            slices.append(AlgoSlice(
                slice_id=str(uuid4()),
                parent_algo_id=parent_algo_id,
                symbol=config.symbol,
                direction=config.direction,
                price=config.price_limit,
                volume=vol,
                scheduled_at=now + interval * i,
            ))

        return slices

    @staticmethod
    def _round_volume(volume: int, direction: OrderDirection) -> int:
        """取整到 100 的整数倍（买入必须为 100 的倍数）。"""
        if direction == OrderDirection.BUY:
            return max((volume // 100) * 100, 100)
        return max(volume, 1)
