from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.domain.strategy.pool.value_objects.ml_model_version import MLModelVersion
from src.domain.strategy.pool.value_objects.performance_snapshot import PerformanceSnapshot
from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating
from src.domain.strategy.pool.value_objects.strategy_status import StrategyStatus

_VALID_TRANSITIONS: dict[StrategyStatus, set[StrategyStatus]] = {
    StrategyStatus.CANDIDATE: {StrategyStatus.ACTIVE, StrategyStatus.RETIRED},
    StrategyStatus.ACTIVE: {StrategyStatus.PAUSED, StrategyStatus.SUSPENDED, StrategyStatus.RETIRED},
    StrategyStatus.PAUSED: {StrategyStatus.ACTIVE, StrategyStatus.RETIRED},
    StrategyStatus.SUSPENDED: {StrategyStatus.ACTIVE, StrategyStatus.RETIRED},
    StrategyStatus.RETIRED: set(),
}

_VALID_STRATEGY_TYPES = {"bar", "cross_section", "ml"}


@dataclass(slots=True, kw_only=True)
class StrategyPoolEntry:
    """策略池条目（充血模型）。

    管理单个策略的完整生命周期：注册 -> 评级 -> 监控 -> 下线。
    """

    strategy_name: str
    strategy_type: str  # "bar" | "cross_section" | "ml"
    description: str
    registered_at: datetime
    status: StrategyStatus = StrategyStatus.CANDIDATE
    rating: StrategyRating = StrategyRating.C
    params: dict[str, Any] = field(default_factory=dict)
    snapshots: list[PerformanceSnapshot] = field(default_factory=list)
    ml_versions: list[MLModelVersion] = field(default_factory=list)
    notes: str = ""

    def __post_init__(self) -> None:
        if self.strategy_type not in _VALID_STRATEGY_TYPES:
            raise ValueError(
                f"Invalid strategy_type: {self.strategy_type!r}, "
                f"must be one of {_VALID_STRATEGY_TYPES}"
            )

    # -- 状态转换方法 --

    def _transition_to(self, target: StrategyStatus, action: str) -> None:
        allowed = _VALID_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise ValueError(
                f"Invalid status transition: {self.status} -> {target} "
                f"(allowed: {allowed or 'none'})"
            )
        self.status = target

    def activate(self) -> None:
        self._transition_to(StrategyStatus.ACTIVE, "activate")

    def pause(self, reason: str = "") -> None:
        self._transition_to(StrategyStatus.PAUSED, "pause")
        if reason:
            self.notes = reason

    def suspend(self, reason: str = "") -> None:
        self._transition_to(StrategyStatus.SUSPENDED, "suspend")
        if reason:
            self.notes = reason

    def retire(self, reason: str = "") -> None:
        self._transition_to(StrategyStatus.RETIRED, "retire")
        if reason:
            self.notes = reason

    # -- 评估方法 --

    def add_snapshot(self, snapshot: PerformanceSnapshot) -> None:
        self.snapshots.append(snapshot)

    def update_rating(self, rating: StrategyRating) -> None:
        self.rating = rating

    # -- 查询方法 --

    @property
    def latest_snapshot(self) -> PerformanceSnapshot | None:
        return self.snapshots[-1] if self.snapshots else None

    @property
    def is_tradeable(self) -> bool:
        return self.status == StrategyStatus.ACTIVE

    @property
    def should_auto_retire(self) -> bool:
        """检查是否应自动标记为待下线。

        条件（满足任一）:
        - 最新快照连续跑输基准 >= 4 周（underperform_weeks 累计计数器）
        - 最近 4 周快照评级均为 D
        """
        if not self.snapshots:
            return False
        # 连续跑输基准 4 周（累计计数器达到 4）
        if self.snapshots[-1].underperform_weeks >= 4:
            return True
        # 连续 4 周评级 D
        if len(self.snapshots) >= 4:
            recent = self.snapshots[-4:]
            if all(s.rating == StrategyRating.D for s in recent):
                return True
        return False

    @property
    def active_model_version(self) -> MLModelVersion | None:
        for v in self.ml_versions:
            if v.is_active:
                return v
        return None

    # -- ML 版本管理 --

    def add_model_version(self, version: MLModelVersion) -> None:
        self.ml_versions.append(version)

    def activate_model_version(self, version_id: str) -> None:
        found = False
        new_versions: list[MLModelVersion] = []
        for v in self.ml_versions:
            if v.version_id == version_id:
                found = True
                new_versions.append(
                    MLModelVersion(
                        version_id=v.version_id,
                        model_type=v.model_type,
                        trained_at=v.trained_at,
                        training_samples=v.training_samples,
                        feature_count=v.feature_count,
                        metrics=v.metrics,
                        is_active=True,
                        notes=v.notes,
                    )
                )
            else:
                if v.is_active:
                    new_versions.append(
                        MLModelVersion(
                            version_id=v.version_id,
                            model_type=v.model_type,
                            trained_at=v.trained_at,
                            training_samples=v.training_samples,
                            feature_count=v.feature_count,
                            metrics=v.metrics,
                            is_active=False,
                            notes=v.notes,
                        )
                    )
                else:
                    new_versions.append(v)
        if not found:
            raise ValueError(f"Model version not found: {version_id}")
        self.ml_versions = new_versions

    def rollback_model_version(self) -> str | None:
        """回滚到上一个活跃版本。

        找到当前活跃版本，将其设为非活跃，
        然后将列表中它前面的一个版本设为活跃。
        返回新激活的版本 ID，如果没有可回滚的版本则返回 None。
        """
        active_idx: int | None = None
        for i, v in enumerate(self.ml_versions):
            if v.is_active:
                active_idx = i
                break
        if active_idx is None or active_idx == 0:
            return None

        prev_idx = active_idx - 1
        new_versions: list[MLModelVersion] = []
        for i, v in enumerate(self.ml_versions):
            if i == active_idx:
                new_versions.append(
                    MLModelVersion(
                        version_id=v.version_id,
                        model_type=v.model_type,
                        trained_at=v.trained_at,
                        training_samples=v.training_samples,
                        feature_count=v.feature_count,
                        metrics=v.metrics,
                        is_active=False,
                        notes=v.notes,
                    )
                )
            elif i == prev_idx:
                new_versions.append(
                    MLModelVersion(
                        version_id=v.version_id,
                        model_type=v.model_type,
                        trained_at=v.trained_at,
                        training_samples=v.training_samples,
                        feature_count=v.feature_count,
                        metrics=v.metrics,
                        is_active=True,
                        notes=v.notes,
                    )
                )
            else:
                new_versions.append(v)
        self.ml_versions = new_versions
        return self.ml_versions[prev_idx].version_id
