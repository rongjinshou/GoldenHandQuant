import logging
from datetime import datetime
from uuid import uuid4

from src.domain.portfolio.entities.order_target import OrderTarget
from src.domain.risk.services.risk_chain import RiskChain
from src.domain.trade.entities.order import Order
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.trade.interfaces.gateways.trade_gateway import ITradeGateway
from src.domain.trade.value_objects.execution_record import ExecutionRecord
from src.domain.trade.value_objects.execution_status import ExecutionStatus
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_status import OrderStatus
from src.domain.trade.value_objects.order_type import OrderType

logger = logging.getLogger(__name__)


class OrderExecutor:
    """自动下单执行器。

    职责:
    - 卖出优先排序
    - 风控检查 (RiskChain)
    - 下单执行
    - 执行结果记录
    """

    def __init__(
        self,
        trade_gateway: ITradeGateway,
        risk_chain: RiskChain,
    ) -> None:
        self._trade_gateway = trade_gateway
        self._risk_chain = risk_chain

    def execute(self, targets: list[OrderTarget]) -> list[ExecutionRecord]:
        """执行订单目标列表。

        流程:
        1. 卖出优先排序
        2. 逐单风控检查
        3. 下单并记录
        """
        sorted_targets = self._sort_sell_first(targets)
        records: list[ExecutionRecord] = []

        for target in sorted_targets:
            record = self._execute_single(target)
            records.append(record)

        return records

    def _sort_sell_first(
        self, targets: list[OrderTarget],
    ) -> list[OrderTarget]:
        """卖出订单优先于买入订单执行。"""
        sells = [t for t in targets if t.direction == OrderDirection.SELL]
        buys = [t for t in targets if t.direction == OrderDirection.BUY]
        return sells + buys

    def _execute_single(self, target: OrderTarget) -> ExecutionRecord:
        """执行单个订单目标。"""
        order = Order(
            order_id=str(uuid4()),
            account_id="",
            ticker=target.symbol,
            direction=target.direction,
            price=target.price,
            volume=target.volume,
            type=OrderType.LIMIT,
            status=OrderStatus.CREATED,
        )

        submitted_at = datetime.now()

        # 风控检查
        risk_result = self._risk_chain.check(order)
        if not risk_result.passed:
            logger.warning(
                "订单被风控拦截: %s %s - %s",
                target.symbol, target.direction, risk_result.reason,
            )
            return ExecutionRecord(
                order_id=order.order_id,
                symbol=target.symbol,
                direction=target.direction,
                target_price=target.price,
                target_volume=target.volume,
                status=ExecutionStatus.REJECTED,
                error_message=risk_result.reason,
                strategy_name=target.strategy_name,
                submitted_at=submitted_at,
            )

        # 下单
        try:
            order_id = self._trade_gateway.place_order(order)
            logger.info(
                "订单已提交: %s %s %s @ %.2f x %d",
                order_id, target.symbol, target.direction,
                target.price, target.volume,
            )
            return ExecutionRecord(
                order_id=str(order_id),
                symbol=target.symbol,
                direction=target.direction,
                target_price=target.price,
                target_volume=target.volume,
                status=ExecutionStatus.SUBMITTED,
                strategy_name=target.strategy_name,
                submitted_at=submitted_at,
            )
        except OrderSubmitError as e:
            logger.error("下单失败: %s - %s", target.symbol, e)
            return ExecutionRecord(
                order_id=order.order_id,
                symbol=target.symbol,
                direction=target.direction,
                target_price=target.price,
                target_volume=target.volume,
                status=ExecutionStatus.FAILED,
                error_message=str(e),
                strategy_name=target.strategy_name,
                submitted_at=submitted_at,
            )
        except Exception as e:
            logger.error("下单异常: %s - %s", target.symbol, e, exc_info=True)
            return ExecutionRecord(
                order_id=order.order_id,
                symbol=target.symbol,
                direction=target.direction,
                target_price=target.price,
                target_volume=target.volume,
                status=ExecutionStatus.FAILED,
                error_message=str(e),
                strategy_name=target.strategy_name,
                submitted_at=submitted_at,
            )
