from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.risk.value_objects.alert import Alert


class ConcentrationRule:
    """集中度告警规则。"""

    def __init__(self, threshold: float = 0.30) -> None:
        self._threshold = threshold

    def evaluate(self, snapshot: MonitorSnapshot) -> Alert | None:
        concentration = snapshot.risk_metrics.max_concentration
        if concentration > self._threshold:
            return Alert(
                level="WARNING",
                category="CONCENTRATION",
                message=f"最大集中度 {concentration:.1%} 超过阈值 {self._threshold:.1%}",
                value=concentration,
                threshold=self._threshold,
            )
        return None
