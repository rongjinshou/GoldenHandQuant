from datetime import datetime

from src.domain.portfolio.interfaces.rebalance_trigger import IRebalanceTrigger


class MonthlyRebalanceTrigger(IRebalanceTrigger):
    """每月再平衡触发器。

    当前日期为月初（day <= 3）且距上次 >= 20 天时触发。
    使用 day <= 3 而非 day == 1，以兼容月初非交易日的情况。
    """

    def __init__(self) -> None:
        self._last_rebalance: datetime | None = None

    def should_rebalance(self, current_date: datetime, last_rebalance: datetime | None) -> bool:
        if last_rebalance is None:
            return True
        if current_date.day > 3:
            return False
        return (current_date.date() - last_rebalance.date()).days >= 20

    def record_rebalance(self, rebalance_date: datetime) -> None:
        self._last_rebalance = rebalance_date
