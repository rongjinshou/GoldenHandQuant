from src.domain.risk.services.base_risk_policy import BaseRiskPolicy
from src.domain.risk.value_objects.risk_check_result import RiskCheckResult
from src.domain.trade.entities.order import Order


class RiskChain(BaseRiskPolicy):
    """风控责任链：按顺序执行多个风控策略，任一不通过即拦截。"""

    def __init__(self, policies: list[BaseRiskPolicy] | None = None) -> None:
        self._policies: list[BaseRiskPolicy] = policies or []

    def add_policy(self, policy: BaseRiskPolicy) -> None:
        self._policies.append(policy)

    def check(self, order: Order) -> RiskCheckResult:
        for policy in self._policies:
            result = policy.check(order)
            if not result.passed:
                return result
        return RiskCheckResult.pass_check()
