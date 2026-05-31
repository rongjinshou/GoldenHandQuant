from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class HealthStatus(StrEnum):
    """执行健康状态。"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class SystemHealthLevel(StrEnum):
    """系统健康级别。"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckResult:
    """单项检查结果。"""

    name: str
    passed: bool
    message: str = ""
    checked_at: datetime = field(default_factory=datetime.now)


@dataclass(slots=True, kw_only=True)
class SystemHealthStatus:
    """系统健康状态值对象。

    聚合各单项检查结果，给出整体健康级别。
    """

    status: SystemHealthLevel
    heartbeat_time: datetime
    uptime_seconds: float
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return self.status == SystemHealthLevel.HEALTHY

    @classmethod
    def from_checks(
        cls,
        checks: list[CheckResult],
        heartbeat_time: datetime,
        uptime_seconds: float,
    ) -> "SystemHealthStatus":
        """根据检查结果推导整体状态。

        规则:
        - 全部通过 -> HEALTHY
        - 有失败但不足半数 -> DEGRADED
        - 半数及以上失败 -> UNHEALTHY
        """
        if not checks:
            status = SystemHealthLevel.HEALTHY
        else:
            failed = sum(1 for c in checks if not c.passed)
            if failed == 0:
                status = SystemHealthLevel.HEALTHY
            elif failed < len(checks) / 2:
                status = SystemHealthLevel.DEGRADED
            else:
                status = SystemHealthLevel.UNHEALTHY

        return cls(
            status=status,
            heartbeat_time=heartbeat_time,
            uptime_seconds=uptime_seconds,
            checks=checks,
        )
