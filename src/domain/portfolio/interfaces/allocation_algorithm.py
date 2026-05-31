from typing import Protocol

from src.domain.portfolio.entities.strategy_allocation import StrategyAllocation
from src.domain.portfolio.entities.strategy_performance import StrategyPerformance


class IAllocationAlgorithm(Protocol):
    """资金分配算法接口。"""

    def calculate(
        self,
        total_capital: float,
        performances: list[StrategyPerformance],
        current_allocations: list[StrategyAllocation] | None = None,
    ) -> list[StrategyAllocation]:
        """计算各策略的资金分配。

        Args:
            total_capital: 可分配总资金。
            performances: 各策略绩效数据。
            current_allocations: 当前分配（用于增量调整，初始分配时为 None）。

        Returns:
            各策略的分配结果列表。权重之和必须为 1.0。
        """
        ...
