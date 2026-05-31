from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class RiskAlertType(StrEnum):
    """风控告警类型。"""
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    PRICE_ANOMALY = "price_anomaly"
    VOLUME_ANOMALY = "volume_anomaly"
    WIDE_SPREAD = "wide_spread"
    RAPID_DROP = "rapid_drop"


class RiskAlertSeverity(StrEnum):
    """风控告警严重程度。"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RiskAlertAction(StrEnum):
    """告警触发后的建议动作。"""
    NONE = "none"
    NOTIFY = "notify"
    CLOSE_POSITION = "close_position"
    PAUSE_TRADING = "pause_trading"


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskAlert:
    """实时风控告警值对象。

    Attributes:
        alert_type: 告警类型。
        severity: 严重程度。
        symbol: 证券代码。
        message: 告警描述。
        timestamp: 触发时间。
        action_required: 建议动作。
        current_price: 当前价格。
        reference_price: 参考价格（止损价/前价等）。
        loss_rate: 亏损比例。
    """

    alert_type: RiskAlertType
    severity: RiskAlertSeverity
    symbol: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    action_required: RiskAlertAction = RiskAlertAction.NOTIFY
    current_price: float = 0.0
    reference_price: float = 0.0
    loss_rate: float = 0.0
