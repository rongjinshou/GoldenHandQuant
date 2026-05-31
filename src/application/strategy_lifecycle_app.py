import logging
from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.portfolio.services.capital_allocation_engine import CapitalAllocationEngine
from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating
from src.domain.strategy.services.strategy_lifecycle_manager import (
    StrategyLifecycleEntry,
    StrategyLifecycleManager,
)
from src.domain.strategy.value_objects.strategy_lifecycle_status import StrategyLifecycleStatus

logger = logging.getLogger(__name__)


class StrategyLifecycleAppService:
    """策略生命周期应用服务。

    编排 注册 → 回测 → 评级 → 自动上线 流水线。
    评级下滑后自动降级（ACTIVE → PAUSED）或下线（RETIRED）。
    与 CapitalAllocationEngine 联动。
    """

    def __init__(
        self,
        lifecycle_manager: StrategyLifecycleManager,
        capital_engine: CapitalAllocationEngine | None = None,
        min_active_rating: StrategyRating = StrategyRating.B,
        total_capital: float = 1_000_000.0,
    ) -> None:
        self._lifecycle = lifecycle_manager
        self._capital_engine = capital_engine
        self._min_active_rating = min_active_rating
        self._total_capital = total_capital

    # -- 注册 + 回测流水线 --

    def register_and_backtest(
        self,
        name: str,
        strategy_type: str,
        description: str,
        params: dict[str, object] | None = None,
    ) -> StrategyLifecycleEntry:
        """注册新策略并启动回测阶段。

        Args:
            name: 策略名称。
            strategy_type: 策略类型。
            description: 策略描述。
            params: 策略参数。

        Returns:
            生命周期条目（状态为 BACKTESTING）。
        """
        entry = self._lifecycle.register_and_backtest(
            name=name,
            strategy_type=strategy_type,
            description=description,
            params=params,
        )
        logger.info("Strategy registered: %s -> BACKTESTING", name)
        return entry

    def complete_backtest(
        self,
        name: str,
        report: BacktestReport,
        benchmark_return: float = 0.0,
        underperform_weeks: int = 0,
    ) -> StrategyLifecycleEntry:
        """回测完成后，进行评级并自动决定上线/暂停。

        评级 >= min_active_rating → ACTIVE（自动触发资金分配）
        评级 < min_active_rating → PAUSED

        Args:
            name: 策略名称。
            report: 回测报告。
            benchmark_return: 基准收益率。
            underperform_weeks: 连续跑输基准周数。

        Returns:
            更新后的生命周期条目。
        """
        entry = self._lifecycle.process_evaluation(
            name=name,
            report=report,
            benchmark_return=benchmark_return,
            underperform_weeks=underperform_weeks,
            min_rating=self._min_active_rating,
        )

        if entry.status == StrategyLifecycleStatus.ACTIVE:
            logger.info(
                "Strategy activated: %s (rating=%s)",
                name, entry.rating,
            )
            self._try_allocate_capital(name)
        else:
            logger.info(
                "Strategy paused: %s (rating=%s, required=%s)",
                name, entry.rating, self._min_active_rating,
            )

        return entry

    # -- 定期检查 --

    def check_performance(
        self,
        active_reports: list[tuple[str, BacktestReport]],
        benchmark_return: float = 0.0,
    ) -> dict[str, list[str]]:
        """定期检查所有活跃策略表现。

        评级下滑后自动降级:
        - D 级 → ACTIVE → PAUSED
        - 连续 4 次 D → RETIRED

        Args:
            active_reports: [(策略名, BacktestReport), ...] 当期回测报告。
            benchmark_return: 基准收益率。

        Returns:
            {"paused": [...], "retired": [...]} 被降级/下线的策略名。
        """
        actions = self._lifecycle.check_performance(
            active_entries=active_reports,
            benchmark_return=benchmark_return,
        )

        if actions["paused"]:
            logger.warning("Auto-paused strategies: %s", actions["paused"])
        if actions["retired"]:
            logger.warning("Auto-retired strategies: %s", actions["retired"])

        return actions

    # -- 查询 --

    def get_lifecycle_status(self, name: str) -> StrategyLifecycleStatus | None:
        """获取策略当前生命周期状态。"""
        entry = self._lifecycle.get_entry(name)
        return entry.status if entry else None

    def get_summary(self) -> dict[str, object]:
        """获取生命周期汇总。"""
        return self._lifecycle.get_summary()

    def get_active_strategies(self) -> list[StrategyLifecycleEntry]:
        """获取所有活跃策略。"""
        return self._lifecycle.get_active_strategies()

    # -- 资金联动 --

    def _try_allocate_capital(self, strategy_name: str) -> None:
        """策略上线后尝试分配资金。

        如果配置了 CapitalAllocationEngine 且有其他活跃策略，
        使用 adjust_for_new_strategy 进行增量分配；
        否则使用 initial_allocate。
        """
        if self._capital_engine is None:
            return

        active = self._lifecycle.get_active_strategies()
        active_names = [e.strategy_name for e in active]

        if len(active_names) <= 1:
            # 首个策略，等权初始分配
            result = self._capital_engine.initial_allocate(
                total_capital=self._total_capital,
                strategy_names=active_names,
            )
            logger.info(
                "Initial capital allocation: %s",
                {a.strategy_name: a.weight for a in result.allocations},
            )
        else:
            # 已有其他策略，增量分配
            # 获取当前分配（从策略池状态推断）
            current_allocations = []
            from src.domain.portfolio.entities.strategy_allocation import StrategyAllocation
            now = datetime.now()
            equal_weight = 1.0 / len(active_names)
            for name in active_names:
                if name != strategy_name:
                    current_allocations.append(
                        StrategyAllocation(
                            strategy_name=name,
                            allocated_capital=round(self._total_capital * equal_weight, 2),
                            weight=equal_weight,
                            allocated_at=now,
                            reason="current",
                        )
                    )

            if current_allocations:
                result = self._capital_engine.adjust_for_new_strategy(
                    total_capital=self._total_capital,
                    new_strategy=strategy_name,
                    current_allocations=current_allocations,
                )
                logger.info(
                    "Adjusted capital allocation for %s: %s",
                    strategy_name,
                    {a.strategy_name: a.weight for a in result.allocations},
                )
