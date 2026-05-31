"""算法订单管理器。

负责算法订单的生命周期管理：创建、拆单、执行跟踪、取消。
"""

import logging
from datetime import datetime
from uuid import uuid4

from src.domain.trade.services.algo_strategies.iceberg_strategy import IcebergStrategy
from src.domain.trade.services.algo_strategies.twap_strategy import TwapStrategy
from src.domain.trade.services.algo_strategies.vwap_strategy import VwapStrategy
from src.domain.trade.value_objects.algo_order_config import AlgoOrderConfig
from src.domain.trade.value_objects.algo_order_status import AlgoOrderStatus
from src.domain.trade.value_objects.algo_progress import AlgoProgress
from src.domain.trade.value_objects.algo_slice import AlgoSlice
from src.domain.trade.value_objects.order_status import OrderStatus

logger = logging.getLogger(__name__)

# 算法类型常量
ALGO_TWAP = "twap"
ALGO_VWAP = "vwap"
ALGO_ICEBERG = "iceberg"


class AlgoOrderManager:
    """算法订单管理器。

    职责:
    - 根据算法类型拆分子单
    - 跟踪算法执行进度
    - 管理子单状态
    """

    def __init__(self) -> None:
        self._twap = TwapStrategy()
        self._vwap = VwapStrategy()
        self._iceberg = IcebergStrategy()
        # algo_id -> (config, slices, status, started_at)
        self._orders: dict[str, _AlgoOrderState] = {}

    def create_algo_order(self, config: AlgoOrderConfig) -> tuple[str, list[AlgoSlice]]:
        """创建算法订单并生成子单。

        Args:
            config: 算法订单配置。

        Returns:
            (algo_id, slices) 算法订单 ID 和拆分后的子单列表。

        Raises:
            ValueError: 如果算法类型不支持。
        """
        algo_id = str(uuid4())
        slices = self._split(config, algo_id)

        self._orders[algo_id] = _AlgoOrderState(
            config=config,
            slices=slices,
            status=AlgoOrderStatus.PENDING,
            started_at=None,
        )

        logger.info(
            "算法订单已创建: %s, 类型=%s, 总量=%d, 子单数=%d",
            algo_id, config.algo_type, config.total_volume, len(slices),
        )
        return algo_id, slices

    def start(self, algo_id: str) -> None:
        """标记算法订单开始执行。"""
        state = self._get_state(algo_id)
        state.status = AlgoOrderStatus.RUNNING
        state.started_at = datetime.now()

    def update_slice_status(self, algo_id: str, slice_id: str, order_id: str, status: OrderStatus) -> None:
        """更新子单状态。

        Args:
            algo_id: 算法订单 ID。
            slice_id: 子单 ID。
            order_id: 实际订单 ID。
            status: 新的订单状态。
        """
        state = self._get_state(algo_id)
        for s in state.slices:
            if s.slice_id == slice_id:
                # AlgoSlice 是 frozen 的，需要替换
                idx = state.slices.index(s)
                state.slices[idx] = AlgoSlice(
                    slice_id=s.slice_id,
                    parent_algo_id=s.parent_algo_id,
                    symbol=s.symbol,
                    direction=s.direction,
                    price=s.price,
                    volume=s.volume,
                    order_id=order_id,
                    status=status,
                    scheduled_at=s.scheduled_at,
                    executed_at=datetime.now() if status == OrderStatus.FILLED else s.executed_at,
                )
                break

        # 检查是否全部完成
        self._check_completion(algo_id)

    def get_progress(self, algo_id: str) -> AlgoProgress:
        """获取算法执行进度。"""
        state = self._get_state(algo_id)
        filled_slices = [s for s in state.slices if s.status == OrderStatus.FILLED]
        filled_volume = sum(s.volume for s in filled_slices)

        # 计算加权平均成交价
        total_value = sum(s.volume * s.price for s in filled_slices)
        avg_price = total_value / filled_volume if filled_volume > 0 else 0.0

        completed_at = None
        if state.status == AlgoOrderStatus.COMPLETED:
            completed_at = max(
                (s.executed_at for s in state.slices if s.executed_at is not None),
                default=None,
            )

        return AlgoProgress(
            algo_id=algo_id,
            total_volume=state.config.total_volume,
            filled_volume=filled_volume,
            remaining_volume=state.config.total_volume - filled_volume,
            avg_fill_price=avg_price,
            num_slices_total=len(state.slices),
            num_slices_filled=len(filled_slices),
            status=state.status,
            started_at=state.started_at,
            completed_at=completed_at,
        )

    def cancel(self, algo_id: str) -> AlgoProgress:
        """取消算法订单。"""
        state = self._get_state(algo_id)
        state.status = AlgoOrderStatus.CANCELED
        return self.get_progress(algo_id)

    def get_pending_slices(self, algo_id: str) -> list[AlgoSlice]:
        """获取待执行的子单列表。"""
        state = self._get_state(algo_id)
        return [s for s in state.slices if s.status == OrderStatus.CREATED]

    def _split(self, config: AlgoOrderConfig, algo_id: str) -> list[AlgoSlice]:
        """根据算法类型拆分子单。"""
        match config.algo_type:
            case "twap":
                return self._twap.generate_slices(config, algo_id)
            case "vwap":
                return self._vwap.generate_slices(config, algo_id)
            case "iceberg":
                return self._iceberg.generate_slices(config, algo_id)
            case _:
                raise ValueError(f"不支持的算法类型: {config.algo_type}")

    def _get_state(self, algo_id: str) -> "_AlgoOrderState":
        """获取算法订单内部状态。"""
        if algo_id not in self._orders:
            raise KeyError(f"算法订单不存在: {algo_id}")
        return self._orders[algo_id]

    def _check_completion(self, algo_id: str) -> None:
        """检查算法订单是否已完成。"""
        state = self._get_state(algo_id)
        if state.status != AlgoOrderStatus.RUNNING:
            return
        all_done = all(
            s.status in (OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED)
            for s in state.slices
        )
        if all_done:
            state.status = AlgoOrderStatus.COMPLETED
            logger.info("算法订单已完成: %s", algo_id)


class _AlgoOrderState:
    """算法订单内部状态（非值对象，仅管理器内部使用）。"""

    __slots__ = ("config", "slices", "status", "started_at")

    def __init__(
        self,
        config: AlgoOrderConfig,
        slices: list[AlgoSlice],
        status: AlgoOrderStatus,
        started_at: datetime | None,
    ) -> None:
        self.config = config
        self.slices = slices
        self.status = status
        self.started_at = started_at
