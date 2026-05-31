from typing import Protocol

from src.domain.risk.value_objects.risk_event import RiskEvent


class IRiskNotifier(Protocol):
    """风控通知接口。"""

    def notify(self, event: RiskEvent) -> None:
        """发送风控通知。"""
        ...
