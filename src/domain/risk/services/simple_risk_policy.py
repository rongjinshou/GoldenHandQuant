from typing import Self

from src.domain.risk.value_objects.risk_check_result import RiskCheckResult
from src.domain.risk.interfaces.policies.risk_policy import RiskPolicy
from src.domain.trade.entities.order import Order


class SimpleRiskPolicy(RiskPolicy):
    """简单的风控策略实现。"""

    def check(self, order: Order) -> RiskCheckResult:
        """检查订单。

        这里仅做简单检查:
        1. 价格必须 > 0
        2. 数量必须 > 0
        """
        if order.price <= 0:
            return RiskCheckResult.reject("Price must be positive")
        if order.volume <= 0:
            return RiskCheckResult.reject("Volume must be positive")
        return RiskCheckResult.pass_check()
