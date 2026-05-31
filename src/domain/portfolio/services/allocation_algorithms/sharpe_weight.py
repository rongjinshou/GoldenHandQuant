from datetime import datetime

from src.domain.portfolio.entities.strategy_allocation import StrategyAllocation
from src.domain.portfolio.entities.strategy_performance import StrategyPerformance
from src.domain.portfolio.interfaces.allocation_algorithm import IAllocationAlgorithm


class SharpeWeightAlgorithm(IAllocationAlgorithm):
    """夏普比率加权分配算法。

    按各策略夏普比率正向加权:
    raw_weight_i = max(sharpe_i, 0) + epsilon   # epsilon=0.01 防止全零
    weight_i = raw_weight_i / sum(raw_weight_j)
    """

    EPSILON: float = 0.01

    def calculate(
        self,
        total_capital: float,
        performances: list[StrategyPerformance],
        current_allocations: list[StrategyAllocation] | None = None,
    ) -> list[StrategyAllocation]:
        if not performances:
            return []

        now = datetime.now()
        raw_weights: list[float] = []
        for perf in performances:
            raw_weights.append(max(perf.sharpe_ratio, 0.0) + self.EPSILON)

        total_raw = sum(raw_weights)
        n = len(performances)

        allocations: list[StrategyAllocation] = []
        for i, perf in enumerate(performances):
            if i == n - 1:
                w = round(1.0 - sum(a.weight for a in allocations), 6)
            else:
                w = round(raw_weights[i] / total_raw, 6)
            allocations.append(
                StrategyAllocation(
                    strategy_name=perf.strategy_name,
                    allocated_capital=round(total_capital * w, 2),
                    weight=w,
                    allocated_at=now,
                    reason="sharpe_weight",
                )
            )

        return allocations
