from typing import Protocol
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.trade.entities.order import Order

class ITradeGateway(Protocol):
    """交易网关接口。
    
    负责向外部交易系统下单。
    """

    def place_order(self, order: Order) -> str:
        """提交订单。

        Args:
            order: 订单实体。

        Returns:
            str: 委托编号 (Order ID)。

        Raises:
            OrderSubmitError: 如果提交失败。
        """
        ...
