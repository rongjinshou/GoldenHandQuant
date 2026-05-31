"""算法交易应用服务。

协调算法订单管理器与算法交易网关，提供算法订单的创建、执行、取消、查询等用例。
"""

import logging

from src.domain.trade.exceptions import TradeError
from src.domain.trade.interfaces.gateways.algo_trader import IAlgoTrader
from src.domain.trade.services.algo_order_manager import AlgoOrderManager
from src.domain.trade.value_objects.algo_order_config import AlgoOrderConfig
from src.domain.trade.value_objects.algo_progress import AlgoProgress
from src.domain.trade.value_objects.order_status import OrderStatus

logger = logging.getLogger(__name__)


class AlgoTradingAppService:
    """算法交易应用服务。

    职责:
    - 接收外部算法下单请求
    - 调用 AlgoOrderManager 拆分子单
    - 调用 IAlgoTrader 执行子单
    - 跟踪执行进度
    """

    def __init__(
        self,
        algo_trader: IAlgoTrader,
        algo_order_manager: AlgoOrderManager | None = None,
    ) -> None:
        self._algo_trader = algo_trader
        self._manager = algo_order_manager or AlgoOrderManager()

    def submit_algo_order(self, config: AlgoOrderConfig) -> AlgoProgress:
        """提交算法订单。

        流程:
        1. 创建算法订单并拆分子单
        2. 调用算法交易网关执行
        3. 返回执行进度

        Args:
            config: 算法订单配置。

        Returns:
            AlgoProgress: 初始执行进度。

        Raises:
            TradeError: 执行失败时抛出。
        """
        try:
            algo_id, slices = self._manager.create_algo_order(config)
            self._manager.start(algo_id)

            progress = self._algo_trader.execute_algo_order(algo_id, config, slices)

            # 同步子单状态到管理器
            for s in slices:
                if s.order_id:
                    self._manager.update_slice_status(
                        algo_id, s.slice_id, s.order_id, OrderStatus.SUBMITTED,
                    )

            logger.info(
                "算法订单已提交: %s, 类型=%s, 子单数=%d",
                algo_id, config.algo_type, len(slices),
            )
            return progress

        except TradeError:
            raise
        except Exception as e:
            logger.error("算法订单提交失败: %s", e, exc_info=True)
            raise TradeError(f"算法订单提交失败: {e}") from e

    def cancel_algo_order(self, algo_id: str) -> AlgoProgress:
        """取消算法订单。

        Args:
            algo_id: 算法订单 ID。

        Returns:
            AlgoProgress: 取消后的执行进度。
        """
        try:
            progress = self._algo_trader.cancel_algo_order(algo_id)
            self._manager.cancel(algo_id)
            logger.info("算法订单已取消: %s", algo_id)
            return progress
        except Exception as e:
            logger.error("取消算法订单失败: %s - %s", algo_id, e, exc_info=True)
            raise TradeError(f"取消算法订单失败: {e}") from e

    def get_progress(self, algo_id: str) -> AlgoProgress:
        """查询算法执行进度。

        Args:
            algo_id: 算法订单 ID。

        Returns:
            AlgoProgress: 当前执行进度。
        """
        return self._manager.get_progress(algo_id)

    def on_slice_filled(
        self, algo_id: str, slice_id: str, order_id: str,
    ) -> AlgoProgress:
        """子单成交回调。

        当基础设施层收到子单成交回报时调用此方法更新进度。

        Args:
            algo_id: 算法订单 ID。
            slice_id: 子单 ID。
            order_id: 实际订单 ID。

        Returns:
            AlgoProgress: 更新后的执行进度。
        """
        self._manager.update_slice_status(algo_id, slice_id, order_id, OrderStatus.FILLED)
        progress = self._manager.get_progress(algo_id)
        logger.info(
            "子单已成交: algo=%s, slice=%s, 进度=%.1f%%",
            algo_id, slice_id, progress.fill_ratio * 100,
        )
        return progress
