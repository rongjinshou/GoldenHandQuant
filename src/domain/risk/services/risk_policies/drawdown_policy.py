from src.domain.risk.services.base_risk_policy import BaseRiskPolicy
from src.domain.risk.value_objects.risk_check_result import RiskCheckResult
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.account.entities.asset import Asset
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot


class DrawdownPolicy(BaseRiskPolicy):
    """回撤熔断策略：当日回撤超过阈值时禁止新增买入。"""

    def __init__(self, snapshots: list[DailySnapshot], asset: Asset, max_drawdown: float = 0.2) -> None:
        self._snapshots = snapshots
        self._asset = asset
        self._max_drawdown = max_drawdown

    def check(self, order: Order) -> RiskCheckResult:
        if order.direction != OrderDirection.BUY:
            return RiskCheckResult.pass_check()
        if not self._snapshots:
            return RiskCheckResult.pass_check()

        peak = self._snapshots[0].total_asset
        for s in self._snapshots:
            if s.total_asset > peak:
                peak = s.total_asset
        current_dd = (peak - self._asset.total_asset) / peak if peak > 0 else 0.0
        if current_dd > self._max_drawdown:
            return RiskCheckResult.reject(
                f"Drawdown limit breached: {current_dd:.2%} > {self._max_drawdown:.2%}"
            )
        return RiskCheckResult.pass_check()
