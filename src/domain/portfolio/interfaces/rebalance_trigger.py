from abc import ABC, abstractmethod
from datetime import datetime


class IRebalanceTrigger(ABC):
    """再平衡触发器接口。"""

    @abstractmethod
    def should_rebalance(self, current_date: datetime, last_rebalance: datetime | None) -> bool:
        """判断是否应触发再平衡。

        Args:
            current_date: 当前日期。
            last_rebalance: 上次再平衡时间，首次为 None。

        Returns:
            是否应触发再平衡。
        """
        ...

    @abstractmethod
    def record_rebalance(self, rebalance_date: datetime) -> None:
        """记录再平衡时间。"""
        ...
