"""冰山单 (Iceberg Order) 算法策略。

隐藏真实委托数量，每次只在盘口显示一小部分（display_volume），
成交后再补充挂单，直到总量全部成交。
"""

from datetime import datetime, timedelta
from uuid import uuid4

from src.domain.trade.value_objects.algo_order_config import AlgoOrderConfig
from src.domain.trade.value_objects.algo_slice import AlgoSlice
from src.domain.trade.value_objects.order_direction import OrderDirection


class IcebergStrategy:
    """冰山单策略。

    将大额订单拆分为若干 display_volume 大小的子单，
    每次只挂出一个子单，成交后再挂下一个，直到全部成交。
    子单的 scheduled_at 依次递增，由执行器按顺序处理。
    """

    def generate_slices(
        self,
        config: AlgoOrderConfig,
        parent_algo_id: str,
        start_time: datetime | None = None,
    ) -> list[AlgoSlice]:
        """生成冰山单子单列表。

        Args:
            config: 算法订单配置。display_volume 决定每次挂单量。
            parent_algo_id: 父算法订单 ID。
            start_time: 基准时间，默认为当前时间。

        Returns:
            拆分后的子单列表（按顺序执行，后一个依赖前一个成交）。
        """
        now = start_time or datetime.now()
        display_vol = self._round_volume(config.display_volume, config.direction)
        remaining = config.total_volume
        slices: list[AlgoSlice] = []
        seq = 0

        while remaining > 0:
            vol = min(display_vol, remaining)
            vol = self._round_volume(vol, config.direction)
            if vol <= 0:
                break

            slices.append(AlgoSlice(
                slice_id=str(uuid4()),
                parent_algo_id=parent_algo_id,
                symbol=config.symbol,
                direction=config.direction,
                price=config.price_limit,
                volume=vol,
                # 冰山单：后一单的计划时间设为前一单之后，确保顺序执行
                scheduled_at=now + timedelta(seconds=seq),
            ))

            remaining -= vol
            seq += 1

        return slices

    @staticmethod
    def _round_volume(volume: int, direction: OrderDirection) -> int:
        """取整到 100 的整数倍（买入必须为 100 的倍数）。"""
        if direction == OrderDirection.BUY:
            return max((volume // 100) * 100, 100)
        return max(volume, 1)
