"""TWAP (Time-Weighted Average Price) 算法策略。

将大额订单按时间均匀拆分为多个小单，等间隔执行，
使成交均价趋近于时间加权平均价格。
"""

from datetime import datetime, timedelta
from uuid import uuid4

from src.domain.trade.value_objects.algo_order_config import AlgoOrderConfig
from src.domain.trade.value_objects.algo_slice import AlgoSlice
from src.domain.trade.value_objects.order_direction import OrderDirection


class TwapStrategy:
    """TWAP 策略：时间加权平均价格算法。

    将大额订单拆分为 N 个等量子单，按等时间间隔执行。
    最后一个子单接收余数，确保总量精确。
    """

    def generate_slices(
        self,
        config: AlgoOrderConfig,
        parent_algo_id: str,
        start_time: datetime | None = None,
    ) -> list[AlgoSlice]:
        """生成 TWAP 子单列表。

        Args:
            config: 算法订单配置。
            parent_algo_id: 父算法订单 ID。
            start_time: 开始时间，默认为当前时间。

        Returns:
            拆分后的子单列表。
        """
        now = start_time or datetime.now()
        num_slices = config.num_slices
        base_volume = self._round_volume(config.total_volume // num_slices, config.direction)
        remainder = config.total_volume - base_volume * num_slices

        interval = timedelta(minutes=config.duration_minutes / num_slices)
        slices: list[AlgoSlice] = []

        for i in range(num_slices):
            # 最后一个子单加上余数
            vol = base_volume
            if i == num_slices - 1 and remainder > 0:
                vol += remainder
                vol = self._round_volume(vol, config.direction)

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
