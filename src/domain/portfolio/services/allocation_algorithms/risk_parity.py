from datetime import datetime

from src.domain.portfolio.entities.strategy_allocation import StrategyAllocation
from src.domain.portfolio.entities.strategy_performance import StrategyPerformance
from src.domain.portfolio.interfaces.allocation_algorithm import IAllocationAlgorithm


class RiskParityAlgorithm(IAllocationAlgorithm):
    """风险平价分配算法。

    各策略对组合风险的贡献相等:
    vol_inv_i = 1 / max(volatility_i, 0.001)
    weight_i = vol_inv_i / sum(vol_inv_j)
    """

    MIN_VOLATILITY: float = 0.001

    def calculate(
        self,
        total_capital: float,
        performances: list[StrategyPerformance],
        current_allocations: list[StrategyAllocation] | None = None,
    ) -> list[StrategyAllocation]:
        if not performances:
            return []

        now = datetime.now()
        vol_inverses: list[float] = []
        for perf in performances:
            vol_inverses.append(1.0 / max(perf.volatility, self.MIN_VOLATILITY))

        total_inv = sum(vol_inverses)
        n = len(performances)

        allocations: list[StrategyAllocation] = []
        for i, perf in enumerate(performances):
            if i == n - 1:
                w = round(1.0 - sum(a.weight for a in allocations), 6)
            else:
                w = round(vol_inverses[i] / total_inv, 6)
            allocations.append(
                StrategyAllocation(
                    strategy_name=perf.strategy_name,
                    allocated_capital=round(total_capital * w, 2),
                    weight=w,
                    allocated_at=now,
                    reason="risk_parity",
                )
            )

        return allocations
