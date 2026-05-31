from datetime import datetime

from src.domain.portfolio.entities.strategy_allocation import StrategyAllocation
from src.domain.portfolio.entities.strategy_performance import StrategyPerformance
from src.domain.portfolio.interfaces.allocation_algorithm import IAllocationAlgorithm


class EqualWeightAlgorithm(IAllocationAlgorithm):
    """等权分配算法。

    每个策略分配相同的权重: weight_i = 1 / N。
    """

    def calculate(
        self,
        total_capital: float,
        performances: list[StrategyPerformance],
        current_allocations: list[StrategyAllocation] | None = None,
    ) -> list[StrategyAllocation]:
        if not performances:
            return []

        now = datetime.now()
        n = len(performances)
        weight = round(1.0 / n, 6)

        allocations: list[StrategyAllocation] = []
        for i, perf in enumerate(performances):
            # 最后一个策略补齐浮点误差
            if i == n - 1:
                w = round(1.0 - sum(a.weight for a in allocations), 6)
            else:
                w = weight
            allocations.append(
                StrategyAllocation(
                    strategy_name=perf.strategy_name,
                    allocated_capital=round(total_capital * w, 2),
                    weight=w,
                    allocated_at=now,
                    reason="equal_weight",
                )
            )

        return allocations
