from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.domain.strategy.pool.services.pool_manager import PoolManager
from src.domain.strategy.pool.services.rating_engine import RatingEngine
from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating
from src.domain.strategy.value_objects.strategy_lifecycle_status import StrategyLifecycleStatus

# 合法状态转换
_VALID_TRANSITIONS: dict[StrategyLifecycleStatus, set[StrategyLifecycleStatus]] = {
    StrategyLifecycleStatus.CANDIDATE: {
        StrategyLifecycleStatus.BACKTESTING,
        StrategyLifecycleStatus.RETIRED,
    },
    StrategyLifecycleStatus.BACKTESTING: {
        StrategyLifecycleStatus.EVALUATING,
        StrategyLifecycleStatus.CANDIDATE,  # 回测失败回退
        StrategyLifecycleStatus.RETIRED,
    },
    StrategyLifecycleStatus.EVALUATING: {
        StrategyLifecycleStatus.ACTIVE,
        StrategyLifecycleStatus.PAUSED,
        StrategyLifecycleStatus.RETIRED,
    },
    StrategyLifecycleStatus.ACTIVE: {
        StrategyLifecycleStatus.PAUSED,
        StrategyLifecycleStatus.RETIRED,
    },
    StrategyLifecycleStatus.PAUSED: {
        StrategyLifecycleStatus.ACTIVE,
        StrategyLifecycleStatus.RETIRED,
    },
    StrategyLifecycleStatus.RETIRED: set(),  # 终态
}


@dataclass(slots=True, kw_only=True)
class StrategyLifecycleEntry:
    """策略生命周期条目。"""

    strategy_name: str
    status: StrategyLifecycleStatus = StrategyLifecycleStatus.CANDIDATE
    rating: StrategyRating = StrategyRating.C
    params: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    reason: str = ""

    def transition_to(self, target: StrategyLifecycleStatus, reason: str = "") -> None:
        """执行状态转换，非法转换抛 ValueError。"""
        allowed = _VALID_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise ValueError(
                f"Invalid lifecycle transition: {self.status} -> {target} "
                f"(allowed: {allowed or 'none'})"
            )
        self.status = target
        self.updated_at = datetime.now()
        if reason:
            self.reason = reason

    def update_rating(self, rating: StrategyRating, reason: str = "") -> None:
        """更新评级。"""
        self.rating = rating
        self.updated_at = datetime.now()
        if reason:
            self.reason = reason


# 评级自动降级阈值: D 级暂停, 连续 4 次 D 级下线
_RATING_DEMOTE_THRESHOLD = StrategyRating.D
_RATING_RETIRE_CONSECUTIVE = 4


class StrategyLifecycleManager:
    """策略生命周期管理器 (领域服务)。

    负责:
    - 注册新策略并推进到回测阶段
    - 处理回测评估结果，联动评级引擎
    - 定期检查活跃策略表现，自动降级/下线
    - 与 PoolManager 和 CapitalAllocationEngine 联动
    """

    def __init__(
        self,
        pool_manager: PoolManager,
        rating_engine: RatingEngine | None = None,
    ) -> None:
        self._pool_manager = pool_manager
        self._rating_engine = rating_engine or RatingEngine()
        self._entries: dict[str, StrategyLifecycleEntry] = {}

    # -- 注册与回测 --

    def register_and_backtest(
        self,
        name: str,
        strategy_type: str,
        description: str,
        params: dict[str, Any] | None = None,
    ) -> StrategyLifecycleEntry:
        """注册新策略并推进到回测阶段。

        同时在策略池中注册为 CANDIDATE，生命周期状态转为 BACKTESTING。

        Args:
            name: 策略名称（需已在 registry 中注册）。
            strategy_type: 策略类型。
            description: 策略描述。
            params: 策略参数。

        Returns:
            创建的生命周期条目（状态为 BACKTESTING）。
        """
        # 同步注册到策略池
        self._pool_manager.register(
            name=name,
            strategy_type=strategy_type,
            description=description,
            params=params,
        )

        entry = StrategyLifecycleEntry(
            strategy_name=name,
            params=params or {},
        )
        entry.transition_to(
            StrategyLifecycleStatus.BACKTESTING,
            reason="registered and entering backtest",
        )
        self._entries[name] = entry
        return entry

    # -- 评估与上线 --

    def process_evaluation(
        self,
        name: str,
        report: Any,  # BacktestReport
        benchmark_return: float = 0.0,
        underperform_weeks: int = 0,
        min_rating: StrategyRating = StrategyRating.B,
    ) -> StrategyLifecycleEntry:
        """处理回测评估结果。

        根据评级决定是否上线：
        - 评级 >= min_rating → ACTIVE
        - 评级 < min_rating → PAUSED

        同步更新策略池评级。

        Args:
            name: 策略名称。
            report: 回测报告。
            benchmark_return: 基准收益率。
            underperform_weeks: 连续跑输基准周数。
            min_rating: 上线最低评级要求。

        Returns:
            更新后的生命周期条目。
        """
        entry = self._get_entry(name)

        # 先转为 EVALUATING
        if entry.status == StrategyLifecycleStatus.BACKTESTING:
            entry.transition_to(
                StrategyLifecycleStatus.EVALUATING,
                reason="backtest completed, evaluating",
            )

        # 联动策略池评估
        pool_entry = self._pool_manager.evaluate_strategy(
            name=name,
            report=report,
            benchmark_return=benchmark_return,
            underperform_weeks=underperform_weeks,
        )
        rating = pool_entry.rating
        entry.update_rating(rating, reason=f"evaluation score: {rating}")

        # 根据评级决定上线/暂停
        rating_order = list(StrategyRating)
        if rating_order.index(rating) <= rating_order.index(min_rating):
            entry.transition_to(
                StrategyLifecycleStatus.ACTIVE,
                reason=f"rating {rating} meets minimum {min_rating}",
            )
            pool_entry.activate()
            self._pool_manager._repo.save(pool_entry)
        else:
            entry.transition_to(
                StrategyLifecycleStatus.PAUSED,
                reason=f"rating {rating} below minimum {min_rating}",
            )

        return entry

    # -- 定期检查 --

    def check_performance(
        self,
        active_entries: list[tuple[str, Any]] | None = None,
        benchmark_return: float = 0.0,
    ) -> dict[str, list[str]]:
        """定期检查所有活跃策略表现，自动降级或下线。

        规则:
        - 评级 D → 暂停 (ACTIVE → PAUSED)
        - 连续 4 次评级 D → 下线 (→ RETIRED)

        Args:
            active_entries: [(策略名, BacktestReport), ...] 为 None 时只检查现有状态。
            benchmark_return: 基准收益率。

        Returns:
            {"paused": [...], "retired": [...]} 被降级/下线的策略名列表。
        """
        actions: dict[str, list[str]] = {"paused": [], "retired": []}

        # 如果提供了新的评估数据，先更新评级
        if active_entries:
            for name, report in active_entries:
                if name not in self._entries:
                    continue
                entry = self._entries[name]
                if entry.status != StrategyLifecycleStatus.ACTIVE:
                    continue

                # 联动策略池评估
                pool_entry = self._pool_manager.evaluate_strategy(
                    name=name,
                    report=report,
                    benchmark_return=benchmark_return,
                )
                entry.update_rating(pool_entry.rating)

        # 检查所有 ACTIVE 条目
        for entry in list(self._entries.values()):
            if entry.status != StrategyLifecycleStatus.ACTIVE:
                continue

            if self._should_retire(entry):
                entry.transition_to(
                    StrategyLifecycleStatus.RETIRED,
                    reason=f"consecutive D ratings (>= {_RATING_RETIRE_CONSECUTIVE})",
                )
                pool_entry = self._pool_manager._repo.find_by_name(entry.strategy_name)
                if pool_entry:
                    pool_entry.retire(reason="auto-retired by lifecycle manager")
                    self._pool_manager._repo.save(pool_entry)
                actions["retired"].append(entry.strategy_name)

            elif entry.rating == _RATING_DEMOTE_THRESHOLD:
                entry.transition_to(
                    StrategyLifecycleStatus.PAUSED,
                    reason=f"rating dropped to {entry.rating}",
                )
                pool_entry = self._pool_manager._repo.find_by_name(entry.strategy_name)
                if pool_entry:
                    pool_entry.pause(reason="auto-paused by lifecycle manager")
                    self._pool_manager._repo.save(pool_entry)
                actions["paused"].append(entry.strategy_name)

        return actions

    def _should_retire(self, entry: StrategyLifecycleEntry) -> bool:
        """检查是否应自动下线（连续 D 评级）。

        通过检查策略池中的快照历史来判断。
        """
        pool_entry = self._pool_manager._repo.find_by_name(entry.strategy_name)
        if pool_entry is None:
            return False
        return pool_entry.should_auto_retire

    # -- 恢复与手动操作 --

    def reactivate(self, name: str) -> StrategyLifecycleEntry:
        """重新激活暂停的策略。"""
        entry = self._get_entry(name)
        entry.transition_to(StrategyLifecycleStatus.ACTIVE, reason="manual reactivation")

        from src.domain.strategy.pool.value_objects.strategy_status import StrategyStatus
        pool_entry = self._pool_manager._repo.find_by_name(name)
        if pool_entry and pool_entry.status != StrategyStatus.ACTIVE:
            pool_entry.activate()
            self._pool_manager._repo.save(pool_entry)

        return entry

    def retire(self, name: str, reason: str = "manual retire") -> StrategyLifecycleEntry:
        """手动下线策略。"""
        entry = self._get_entry(name)
        entry.transition_to(StrategyLifecycleStatus.RETIRED, reason=reason)

        pool_entry = self._pool_manager._repo.find_by_name(name)
        if pool_entry:
            pool_entry.retire(reason=reason)
            self._pool_manager._repo.save(pool_entry)

        return entry

    # -- 查询 --

    def get_entry(self, name: str) -> StrategyLifecycleEntry | None:
        """获取生命周期条目（不抛异常）。"""
        return self._entries.get(name)

    def get_entries_by_status(
        self, status: StrategyLifecycleStatus,
    ) -> list[StrategyLifecycleEntry]:
        """按状态筛选条目。"""
        return [e for e in self._entries.values() if e.status == status]

    def get_active_strategies(self) -> list[StrategyLifecycleEntry]:
        """获取所有活跃策略。"""
        return self.get_entries_by_status(StrategyLifecycleStatus.ACTIVE)

    def get_summary(self) -> dict[str, object]:
        """获取生命周期汇总。"""
        by_status: dict[str, int] = {}
        for entry in self._entries.values():
            by_status[entry.status] = by_status.get(entry.status, 0) + 1
        return {
            "total": len(self._entries),
            "by_status": by_status,
        }

    # -- 内部 --

    def _get_entry(self, name: str) -> StrategyLifecycleEntry:
        """获取条目，不存在则抛 KeyError。"""
        entry = self._entries.get(name)
        if entry is None:
            raise KeyError(f"Strategy not in lifecycle: {name}")
        return entry
