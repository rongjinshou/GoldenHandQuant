from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.risk.value_objects.alert import Alert


class PositionRatioRule:
    """仓位比例告警规则。"""

    def __init__(self, max_ratio: float = 0.80, min_ratio: float = 0.10) -> None:
        self._max_ratio = max_ratio
        self._min_ratio = min_ratio

    def evaluate(self, snapshot: MonitorSnapshot) -> list[Alert]:
        alerts: list[Alert] = []
        ratio = snapshot.risk_metrics.total_position_ratio
        if ratio > self._max_ratio:
            alerts.append(Alert(
                level="WARNING",
                category="POSITION",
                message=f"总仓位 {ratio:.1%} 超过上限 {self._max_ratio:.1%}",
                value=ratio,
                threshold=self._max_ratio,
            ))
        elif ratio < self._min_ratio:
            alerts.append(Alert(
                level="WARNING",
                category="POSITION",
                message=f"总仓位 {ratio:.1%} 低于下限 {self._min_ratio:.1%}",
                value=ratio,
                threshold=self._min_ratio,
            ))
        return alerts
