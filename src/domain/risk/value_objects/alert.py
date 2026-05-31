from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class Alert:
    """告警信息。"""

    level: str  # "WARNING" | "CRITICAL"
    category: str  # "LOSS" | "CONCENTRATION" | "POSITION"
    message: str
    value: float = 0.0
    threshold: float = 0.0
