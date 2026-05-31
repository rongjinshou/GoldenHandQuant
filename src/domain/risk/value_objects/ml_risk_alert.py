from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class MLRiskAlert:
    """ML 模型风险告警。

    Attributes:
        strategy_name: 策略名称。
        alert_type: 告警类型（"overfitting"、"feature_drift"、"performance_degradation"）。
        severity: 严重程度（"warning"、"critical"）。
        metric_name: 触发告警的指标名称。
        metric_value: 指标当前值。
        threshold: 告警阈值。
        description: 告警描述。
        detected_at: 检测时间。
    """

    strategy_name: str
    alert_type: str
    severity: str
    metric_name: str
    metric_value: float
    threshold: float
    description: str
    detected_at: datetime = datetime.now()
