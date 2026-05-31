from dataclasses import dataclass, field
from datetime import datetime


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

    def with_active(self, is_active: bool) -> "MLModelVersion":
        """返回一个新实例，仅修改 is_active 字段。"""
        from dataclasses import replace
        return replace(self, is_active=is_active)
