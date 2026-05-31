from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.risk.services.base_risk_policy import BaseRiskPolicy
from src.domain.risk.value_objects.risk_check_result import RiskCheckResult
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection


class TotalPositionPolicy(BaseRiskPolicy):
    """总仓位上限策略。

    当总持仓市值占总资产比例超过阈值时，拒绝新增买入。
    """

    def __init__(
        self,
        positions: list[Position],
        asset: Asset,
        current_prices: dict[str, float],
        max_ratio: float = 0.80,
    ) -> None:
        self._positions = positions
        self._asset = asset
        self._current_prices = current_prices
        self._max_ratio = max_ratio

    def check(self, order: Order) -> RiskCheckResult:
        if order.direction != OrderDirection.BUY:
            return RiskCheckResult.pass_check()

        market_value = sum(
            p.total_volume * self._current_prices.get(p.ticker, p.average_cost)
            for p in self._positions
        )
        new_value = market_value + order.price * order.volume
        ratio = new_value / self._asset.total_asset if self._asset.total_asset > 0 else 0

        if ratio > self._max_ratio:
            return RiskCheckResult.reject(
                f"Total position {ratio:.2%} exceeds limit {self._max_ratio:.2%}"
            )
        return RiskCheckResult.pass_check()
