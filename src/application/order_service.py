from dataclasses import dataclass
from typing import Self

from src.domain.risk.value_objects.risk_check_result import RiskCheckResult
from src.domain.risk.interfaces.policies.risk_policy import RiskPolicy
from src.domain.trade.interfaces.gateways.trade_gateway import ITradeGateway
from src.domain.trade.entities.order import Order


@dataclass(slots=True, kw_only=True)
class OrderResult:
    """订单结果。

    Attributes:
        success: 是否成功。
        order_id: 订单 ID (若成功)。
        message: 错误信息 (若失败)。
    """

    success: bool
    order_id: str | None = None
    message: str = ""

    @classmethod
    def success(cls, order_id: str) -> Self:
        return cls(success=True, order_id=order_id)

    @classmethod
    def failure(cls, message: str) -> Self:
        return cls(success=False, message=message)


class OrderService:
    """订单服务。

    Attributes:
        _gateway: 交易网关接口。
        _risk_policy: 风控策略接口。
    """

    def __init__(self, gateway: ITradeGateway, risk_policy: RiskPolicy) -> None:
        self._gateway = gateway
        self._risk_policy = risk_policy

    def place_order(self, order: Order) -> OrderResult:
        """提交订单。

        Args:
            order: 订单实体。

        Returns:
            OrderResult: 订单结果。
        """
        # 1. 风控检查
        risk_result = self._risk_policy.check(order)
        if not risk_result.passed:
            return OrderResult.failure(f"Risk check failed: {risk_result.reason}")

        # 2. 提交订单
        try:
            order.submit()
            order_id = self._gateway.place_order(order)
            return OrderResult.success(order_id)
        except Exception as e:
            return OrderResult.failure(f"Order submission failed: {e}")
