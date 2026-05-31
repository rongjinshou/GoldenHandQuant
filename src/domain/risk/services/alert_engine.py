from typing import Protocol

from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.risk.value_objects.alert import Alert


class AlertRule(Protocol):
    """告警规则协议。"""

    def evaluate(self, snapshot: MonitorSnapshot) -> Alert | list[Alert] | None: ...


class AlertEngine:
    """告警规则引擎 — 检查监控快照并生成告警列表。"""

    def __init__(self, rules: list[AlertRule] | None = None) -> None:
        self._rules = rules or []

    def check(self, snapshot: MonitorSnapshot) -> list[Alert]:
        alerts: list[Alert] = []
        for rule in self._rules:
            result = rule.evaluate(snapshot)
            if result is None:
                continue
            if isinstance(result, list):
                alerts.extend(result)
            else:
                alerts.append(result)
        return alerts
