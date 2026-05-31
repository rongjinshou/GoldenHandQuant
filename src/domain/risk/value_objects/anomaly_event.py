from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AnomalyType(StrEnum):
    """异常类型。"""
    STRATEGY = "strategy"
    DATA = "data"
    MARKET = "market"
    ML_MODEL = "ml_model"


class AnomalySeverity(StrEnum):
    """异常严重程度。"""
    WARNING = "warning"
    CRITICAL = "critical"


class AutoAction(StrEnum):
    """自动暂停动作。"""
    NONE = "none"
    PAUSE_STRATEGY = "pause_strategy"
    PAUSE_ALL = "pause_all"


@dataclass(frozen=True, slots=True, kw_only=True)
class AnomalyEvent:
    """异常事件值对象。"""

    anomaly_type: AnomalyType
    severity: AnomalySeverity
    source: str
    message: str
    metric_value: float
    threshold: float
    detected_at: datetime = field(default_factory=datetime.now)
    auto_action: AutoAction = AutoAction.NONE
