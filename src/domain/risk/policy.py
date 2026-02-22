from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Self

from src.domain.trade.order import Order


@dataclass(slots=True, kw_only=True)
class RiskCheckResult:
    """风控检查结果。

    Attributes:
        passed: 是否通过。
        reason: 拒绝原因 (若未通过)。
    """

    passed: bool
    reason: str = ""

    @classmethod
    def pass_check(cls) -> Self:
        return cls(passed=True)

    @classmethod
    def reject(cls, reason: str) -> Self:
        return cls(passed=False, reason=reason)


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
