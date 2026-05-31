from dataclasses import dataclass, field, replace
from datetime import datetime

from src.domain.strategy.value_objects.model_deployment_strategy import (
    ModelDeploymentStrategy,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class MLModelVersion:
    """ML 模型版本元数据（不可变值对象）。"""

    version_id: str
    model_type: str  # "lightgbm" | "xgboost" | "catboost"
    trained_at: datetime
    training_samples: int
    feature_count: int
    metrics: dict[str, float] = field(default_factory=dict)
    is_active: bool = False
    notes: str = ""
    deployment: ModelDeploymentStrategy = ModelDeploymentStrategy.FULL_ROLLOUT
    traffic_percentage: float = 1.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.traffic_percentage <= 1.0):
            raise ValueError(
                f"traffic_percentage must be in [0.0, 1.0], got {self.traffic_percentage}"
            )

    def with_active(self, is_active: bool) -> "MLModelVersion":
        """返回一个新实例，仅修改 is_active 字段。"""
        return replace(self, is_active=is_active)

    def with_deployment(
        self,
        deployment: ModelDeploymentStrategy,
        traffic_percentage: float = 1.0,
    ) -> "MLModelVersion":
        """返回一个新实例，仅修改部署策略和流量比例。"""
        return replace(
            self,
            deployment=deployment,
            traffic_percentage=traffic_percentage,
        )
