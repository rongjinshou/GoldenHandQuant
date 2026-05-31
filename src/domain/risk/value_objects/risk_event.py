from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class RiskEventType(StrEnum):
    """风控事件类型。"""
    DAILY_LOSS_BREACH = "DAILY_LOSS_BREACH"
    DRAWDOWN_BREACH = "DRAWDOWN_BREACH"
    POSITION_LIMIT_BREACH = "POSITION_LIMIT_BREACH"
    STOP_LOSS_TRIGGERED = "STOP_LOSS_TRIGGERED"
    CIRCUIT_BREAKER_ON = "CIRCUIT_BREAKER_ON"
    CIRCUIT_BREAKER_OFF = "CIRCUIT_BREAKER_OFF"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"


class RiskSeverity(StrEnum):
    """风控事件严重级别。"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(slots=True, kw_only=True)
class RiskEvent:
    """风控事件。"""
    event_type: RiskEventType
    severity: RiskSeverity
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
