from typing import Protocol

from src.domain.trade.value_objects.algo_order_config import AlgoOrderConfig
from src.domain.trade.value_objects.algo_progress import AlgoProgress
from src.domain.trade.value_objects.algo_slice import AlgoSlice


class IAlgoTrader(Protocol):
    """算法交易网关接口。

    由基础设施层实现，负责算法订单的执行与管理。
    """

    def execute_algo_order(
        self, algo_id: str, config: AlgoOrderConfig, slices: list[AlgoSlice],
    ) -> AlgoProgress:
        """执行算法订单。

        根据拆分好的子单列表，按算法逻辑逐单提交。

        Args:
            algo_id: 算法订单 ID。
            config: 算法订单配置。
            slices: 拆分好的子单列表。

        Returns:
            AlgoProgress: 算法执行进度。
        """
        ...

    def cancel_algo_order(self, algo_id: str) -> AlgoProgress:
        """取消算法订单。

        撤销所有未成交的子单，返回最终进度。

        Args:
            algo_id: 算法订单 ID。

        Returns:
            AlgoProgress: 取消后的执行进度。
        """
        ...

    def get_progress(self, algo_id: str) -> AlgoProgress:
        """查询算法执行进度。

        Args:
            algo_id: 算法订单 ID。

        Returns:
            AlgoProgress: 当前执行进度。
        """
        ...
