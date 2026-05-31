from enum import StrEnum


class HealthStatus(StrEnum):
    """执行健康状态。"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
