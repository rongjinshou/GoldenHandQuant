from datetime import datetime

from src.domain.portfolio.entities.strategy_allocation import AllocationResult, StrategyAllocation
from src.domain.portfolio.entities.strategy_performance import StrategyPerformance
from src.domain.portfolio.interfaces.allocation_algorithm import IAllocationAlgorithm
from src.domain.portfolio.interfaces.rebalance_trigger import IRebalanceTrigger
from src.domain.portfolio.services.allocation_algorithms.equal_weight import EqualWeightAlgorithm


class CapitalAllocationEngine:
    """资金分配引擎，协调分配算法和再平衡触发。

    Attributes:
        algorithm: 分配算法。
        trigger: 再平衡触发器。
        max_single_weight: 单策略最大权重。
        min_single_weight: 单策略最小权重。
        max_weight_change: 单次再平衡最大权重变化幅度。
        min_lookback_days: 最小回看天数，不足时回退等权。
    """

    def __init__(
        self,
        algorithm: IAllocationAlgorithm,
        trigger: IRebalanceTrigger,
        max_single_weight: float = 0.40,
        min_single_weight: float = 0.05,
        max_weight_change: float = 0.10,
        min_lookback_days: int = 20,
    ) -> None:
        self._algorithm = algorithm
        self._trigger = trigger
        self._max_single_weight = max_single_weight
        self._min_single_weight = min_single_weight
        self._max_weight_change = max_weight_change
        self._min_lookback_days = min_lookback_days
        self._equal_weight = EqualWeightAlgorithm()

    @property
    def trigger(self) -> IRebalanceTrigger:
        return self._trigger

    def initial_allocate(
        self,
        total_capital: float,
        strategy_names: list[str],
    ) -> AllocationResult:
        """新策略上线时的初始分配（等权）。

        Args:
            total_capital: 可分配总资金。
            strategy_names: 策略名称列表。

        Returns:
            初始分配结果。
        """
        now = datetime.now()
        performances = [
            StrategyPerformance(
                strategy_name=name,
                total_return=0.0,
                annualized_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                volatility=0.0,
                lookback_days=0,
                updated_at=now,
            )
            for name in strategy_names
        ]

        allocations = self._equal_weight.calculate(total_capital, performances)
        allocations = self._apply_constraints(allocations)

        return AllocationResult(
            total_capital=total_capital,
            allocations=allocations,
            algorithm="equal_weight_initial",
            created_at=now,
        )

    def rebalance(
        self,
        total_capital: float,
        performances: list[StrategyPerformance],
        current_allocations: list[StrategyAllocation],
        current_date: datetime,
    ) -> AllocationResult | None:
        """检查并执行再平衡。返回 None 表示不需要再平衡。

        Args:
            total_capital: 可分配总资金。
            performances: 各策略绩效数据。
            current_allocations: 当前分配。
            current_date: 当前日期。

        Returns:
            再平衡结果，或 None。
        """
        last_rebalance = current_allocations[0].allocated_at if current_allocations else None
        if not self._trigger.should_rebalance(current_date, last_rebalance):
            return None

        # 绩效数据不足时回退等权
        insufficient = any(p.lookback_days < self._min_lookback_days for p in performances)
        if insufficient or not performances:
            algorithm = self._equal_weight
            algo_name = "equal_weight_fallback"
        else:
            algorithm = self._algorithm
            algo_name = self._algorithm.__class__.__name__

        new_allocations = algorithm.calculate(total_capital, performances, current_allocations)
        new_allocations = self._apply_constraints(new_allocations)
        new_allocations = self._apply_gradual_adjustment(new_allocations, current_allocations)

        # 重新计算 allocated_capital 以匹配约束后的权重
        final_allocations = [
            StrategyAllocation(
                strategy_name=a.strategy_name,
                allocated_capital=round(total_capital * a.weight, 2),
                weight=a.weight,
                allocated_at=current_date,
                reason=a.reason,
            )
            for a in new_allocations
        ]

        self._trigger.record_rebalance(current_date)

        return AllocationResult(
            total_capital=total_capital,
            allocations=final_allocations,
            algorithm=algo_name,
            created_at=current_date,
        )

    def adjust_for_new_strategy(
        self,
        total_capital: float,
        new_strategy: str,
        current_allocations: list[StrategyAllocation],
    ) -> AllocationResult:
        """新策略加入时，从现有策略中按比例抽调资金。

        新策略默认权重上限 20%（冷启动保护），不足部分从现有策略按比例缩减。

        Args:
            total_capital: 可分配总资金。
            new_strategy: 新策略名称。
            current_allocations: 当前分配。

        Returns:
            调整后的分配结果。
        """
        now = datetime.now()
        new_strategy_max_weight = 0.20  # 冷启动保护

        # 新策略初始权重 = min(等权, 冷启动上限)
        n_total = len(current_allocations) + 1
        equal_weight = 1.0 / n_total
        new_weight = min(equal_weight, new_strategy_max_weight)

        # 剩余权重分配给现有策略（按原比例缩减）
        remaining_weight = 1.0 - new_weight
        old_weight_sum = sum(a.weight for a in current_allocations)

        new_allocations: list[StrategyAllocation] = []
        for a in current_allocations:
            if old_weight_sum > 0:
                scaled_w = round(a.weight / old_weight_sum * remaining_weight, 6)
            else:
                scaled_w = round(remaining_weight / len(current_allocations), 6)
            new_allocations.append(
                StrategyAllocation(
                    strategy_name=a.strategy_name,
                    allocated_capital=round(total_capital * scaled_w, 2),
                    weight=scaled_w,
                    allocated_at=now,
                    reason="adjust_for_new_strategy",
                )
            )

        # 补齐新策略
        actual_new_weight = round(1.0 - sum(a.weight for a in new_allocations), 6)
        new_allocations.append(
            StrategyAllocation(
                strategy_name=new_strategy,
                allocated_capital=round(total_capital * actual_new_weight, 2),
                weight=actual_new_weight,
                allocated_at=now,
                reason="new_strategy_cold_start",
            )
        )

        return AllocationResult(
            total_capital=total_capital,
            allocations=new_allocations,
            algorithm="adjust_for_new_strategy",
            created_at=now,
        )

    def _apply_constraints(self, allocations: list[StrategyAllocation]) -> list[StrategyAllocation]:
        """应用 max/min 权重约束并重新归一化。

        裁剪到 [min, max] 后按比例归一化，保持各策略间的相对比例。

        Args:
            allocations: 原始分配结果。

        Returns:
            约束后的分配结果。
        """
        if not allocations:
            return []

        # 先裁剪到 [min, max] 范围
        weights = [max(min(a.weight, self._max_single_weight), self._min_single_weight) for a in allocations]

        # 按比例归一化
        total = sum(weights)
        if total <= 0:
            return allocations

        n = len(allocations)
        result: list[StrategyAllocation] = []
        for i, a in enumerate(allocations):
            if i == n - 1:
                w = round(1.0 - sum(r.weight for r in result), 6)
            else:
                w = round(weights[i] / total, 6)
            result.append(
                StrategyAllocation(
                    strategy_name=a.strategy_name,
                    allocated_capital=a.allocated_capital,
                    weight=w,
                    allocated_at=a.allocated_at,
                    reason=a.reason,
                )
            )

        return result

    def _apply_gradual_adjustment(
        self,
        new_allocations: list[StrategyAllocation],
        current_allocations: list[StrategyAllocation],
    ) -> list[StrategyAllocation]:
        """限制单次权重变化幅度（max_weight_change）。

        Args:
            new_allocations: 算法计算的新分配。
            current_allocations: 当前分配。

        Returns:
            渐进调整后的分配。
        """
        if not current_allocations:
            return new_allocations

        current_map = {a.strategy_name: a.weight for a in current_allocations}

        result: list[StrategyAllocation] = []
        for a in new_allocations:
            old_w = current_map.get(a.strategy_name, a.weight)
            diff = a.weight - old_w

            # 限制变化幅度
            if abs(diff) > self._max_weight_change:
                if diff > 0:
                    clamped_w = old_w + self._max_weight_change
                else:
                    clamped_w = old_w - self._max_weight_change
            else:
                clamped_w = a.weight

            clamped_w = round(clamped_w, 6)
            result.append(
                StrategyAllocation(
                    strategy_name=a.strategy_name,
                    allocated_capital=a.allocated_capital,
                    weight=clamped_w,
                    allocated_at=a.allocated_at,
                    reason=a.reason,
                )
            )

        # 按比例归一化（保持各策略间相对比例）
        total = sum(r.weight for r in result)
        if total > 0 and abs(total - 1.0) > 1e-6:
            n = len(result)
            normalized: list[StrategyAllocation] = []
            for i, r in enumerate(result):
                if i == n - 1:
                    w = round(1.0 - sum(nr.weight for nr in normalized), 6)
                else:
                    w = round(r.weight / total, 6)
                normalized.append(
                    StrategyAllocation(
                        strategy_name=r.strategy_name,
                        allocated_capital=r.allocated_capital,
                        weight=w,
                        allocated_at=r.allocated_at,
                        reason=r.reason,
                    )
                )
            result = normalized

        return result
