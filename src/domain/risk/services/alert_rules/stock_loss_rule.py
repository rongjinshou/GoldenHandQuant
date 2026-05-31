from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.risk.value_objects.alert import Alert


class StockLossRule:
    """单只亏损告警规则。"""

    def __init__(self, threshold: float = 0.05) -> None:
        self._threshold = threshold

    def evaluate(self, snapshot: MonitorSnapshot) -> Alert | None:
        for pos in snapshot.positions:
            if pos.pnl_ratio < -self._threshold:
                return Alert(
                    level="WARNING",
                    category="LOSS",
                    message=f"{pos.ticker} 亏损 {pos.pnl_ratio:.2%}，超过阈值 {-self._threshold:.2%}",
                    value=pos.pnl_ratio,
                    threshold=-self._threshold,
                )
        return None
