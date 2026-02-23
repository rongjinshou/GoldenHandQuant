from abc import ABC, abstractmethod
from src.domain.trade.entities.order import Order
from src.domain.risk.value_objects.risk_check_result import RiskCheckResult

class RiskPolicy(ABC):
    """风控策略接口。"""

    @abstractmethod
    def check(self, order: Order) -> RiskCheckResult:
        """检查订单是否符合风控规则。

        Args:
            order: 待检查的订单。

        Returns:
            RiskCheckResult: 检查结果。
        """
        ...
