from datetime import datetime

from src.domain.portfolio.interfaces.rebalance_trigger import IRebalanceTrigger


class DailyRebalanceTrigger(IRebalanceTrigger):
    """每日再平衡触发器。

    每个交易日触发（last_rebalance 为空或日期早于 current_date）。
    """

    def __init__(self) -> None:
        self._last_rebalance: datetime | None = None

    def should_rebalance(self, current_date: datetime, last_rebalance: datetime | None) -> bool:
        if last_rebalance is None:
            return True
        return current_date.date() > last_rebalance.date()

    def record_rebalance(self, rebalance_date: datetime) -> None:
        self._last_rebalance = rebalance_date
