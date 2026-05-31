from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.risk.value_objects.alert import Alert


class DailyLossRule:
    """单日亏损告警规则。"""

    def __init__(self, threshold: float = 0.03) -> None:
        self._threshold = threshold

    def evaluate(self, snapshot: MonitorSnapshot) -> Alert | None:
        if snapshot.yesterday_asset <= 0:
            return None
        pnl_ratio = snapshot.today_pnl_ratio
        if pnl_ratio < -self._threshold:
            return Alert(
                level="CRITICAL",
                category="LOSS",
                message=f"单日亏损 {pnl_ratio:.2%}，超过阈值 {-self._threshold:.2%}",
                value=pnl_ratio,
                threshold=-self._threshold,
            )
        return None
