from datetime import datetime

from src.domain.portfolio.entities.strategy_allocation import StrategyAllocation
from src.domain.portfolio.entities.strategy_performance import StrategyPerformance
from src.domain.portfolio.interfaces.allocation_algorithm import IAllocationAlgorithm


class KellyAllocationAlgorithm(IAllocationAlgorithm):
    """凯利公式分配算法。

    基于凯利公式计算最优资金比例（半凯利）:
    kelly_i = (win_rate_i * pl_ratio_i - (1 - win_rate_i)) / pl_ratio_i
    kelly_i = max(kelly_i, 0) * 0.5   # 半凯利
    weight_i = kelly_i / sum(kelly_j)

    当 profit_loss_ratio 为 0 或不可用时，回退到等权分配。
    """

    KELLY_FRACTION: float = 0.5  # 半凯利

    def calculate(
        self,
        total_capital: float,
        performances: list[StrategyPerformance],
        current_allocations: list[StrategyAllocation] | None = None,
    ) -> list[StrategyAllocation]:
        if not performances:
            return []

        now = datetime.now()

        # 计算各策略的凯利比例
        kelly_values: list[float] = []
        for perf in performances:
            pl_ratio = perf.profit_loss_ratio
            if pl_ratio <= 0:
                # 盈亏比不可用时，凯利值为 0
                kelly_values.append(0.0)
                continue

            kelly = (perf.win_rate * pl_ratio - (1.0 - perf.win_rate)) / pl_ratio
            kelly = max(kelly, 0.0) * self.KELLY_FRACTION
            kelly_values.append(kelly)

        total_kelly = sum(kelly_values)

        # 如果所有凯利值为 0，回退等权
        if total_kelly <= 0:
            n = len(performances)
            weight = round(1.0 / n, 6)
            allocations: list[StrategyAllocation] = []
            for i, perf in enumerate(performances):
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
                        reason="kelly_fallback_equal",
                    )
                )
            return allocations

        n = len(performances)
        allocations = []
        for i, perf in enumerate(performances):
            if i == n - 1:
                w = round(1.0 - sum(a.weight for a in allocations), 6)
            else:
                w = round(kelly_values[i] / total_kelly, 6)
            allocations.append(
                StrategyAllocation(
                    strategy_name=perf.strategy_name,
                    allocated_capital=round(total_capital * w, 2),
                    weight=w,
                    allocated_at=now,
                    reason="kelly_allocation",
                )
            )

        return allocations
