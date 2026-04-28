from src.domain.risk.services.base_risk_policy import BaseRiskPolicy
from src.domain.risk.value_objects.risk_check_result import RiskCheckResult
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.account.entities.position import Position
from src.domain.account.entities.asset import Asset


class PositionLimitPolicy(BaseRiskPolicy):
    """单标的仓位上限策略。"""

    def __init__(self, positions: list[Position], asset: Asset, max_ratio: float = 0.3) -> None:
        self._position_map = {p.ticker: p for p in positions}
        self._asset = asset
        self._max_ratio = max_ratio

    def check(self, order: Order) -> RiskCheckResult:
        if order.direction != OrderDirection.BUY:
            return RiskCheckResult.pass_check()
        current_pos = self._position_map.get(order.ticker)
        current_value = (current_pos.total_volume * current_pos.average_cost) if current_pos else 0.0
        new_value = current_value + order.price * order.volume
        if new_value > self._asset.total_asset * self._max_ratio:
            return RiskCheckResult.reject(
                f"Position limit exceeded: {order.ticker} would be {new_value:.0f}/{self._asset.total_asset:.0f}"
            )
        return RiskCheckResult.pass_check()
