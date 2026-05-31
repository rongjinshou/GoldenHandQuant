from src.domain.risk.services.base_risk_policy import BaseRiskPolicy
from src.domain.risk.services.circuit_breaker import CircuitBreaker
from src.domain.risk.value_objects.risk_check_result import RiskCheckResult
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection


class DailyLossPolicy(BaseRiskPolicy):
    """单日亏损订单级策略。

    当熔断器状态非 NORMAL 时，拒绝非卖出订单。
    """

    def __init__(self, circuit_breaker: CircuitBreaker) -> None:
        self._breaker = circuit_breaker

    def check(self, order: Order) -> RiskCheckResult:
        state = self._breaker.state

        if state.blocks_all_trading:
            return RiskCheckResult.reject(
                f"Circuit breaker active: {state.trigger_reason}"
            )

        if state.allows_sell_only and order.direction == OrderDirection.BUY:
            return RiskCheckResult.reject(
                f"Cooldown period, sell-only: {state.trigger_reason}"
            )

        return RiskCheckResult.pass_check()
