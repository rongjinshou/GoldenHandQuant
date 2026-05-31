from datetime import datetime

from src.domain.portfolio.interfaces.rebalance_trigger import IRebalanceTrigger


class WeeklyRebalanceTrigger(IRebalanceTrigger):
    """每周再平衡触发器。

    当前日期为周一（weekday=0）且距上次 >= 5 天时触发。
    """

    def __init__(self) -> None:
        self._last_rebalance: datetime | None = None

    def should_rebalance(self, current_date: datetime, last_rebalance: datetime | None) -> bool:
        if last_rebalance is None:
            return True
        if current_date.weekday() != 0:  # 0 = Monday
            return False
        return (current_date.date() - last_rebalance.date()).days >= 5

    def record_rebalance(self, rebalance_date: datetime) -> None:
        self._last_rebalance = rebalance_date
