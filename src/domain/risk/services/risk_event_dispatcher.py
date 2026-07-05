import logging

from src.domain.risk.interfaces.notification import IRiskNotifier
from src.domain.risk.value_objects.risk_event import RiskEvent

logger = logging.getLogger(__name__)


class RiskEventDispatcher:
    """风控事件分发器。

    将风控事件广播给所有已注册的通知器。
    """

    def __init__(self) -> None:
        self._notifiers: list[IRiskNotifier] = []

    def add_notifier(self, notifier: IRiskNotifier) -> None:
        self._notifiers.append(notifier)

    def dispatch(self, event: RiskEvent) -> None:
        for notifier in self._notifiers:
            try:
                notifier.notify(event)
            except Exception as e:
                # TD-04 修复: 不再静默吞异常，记录警告日志以保证可观测性
                logger.warning(
                    "通知器 %s 分发失败: %s (event=%s)",
                    type(notifier).__name__, e, event.event_type,
                )

    def dispatch_all(self, events: list[RiskEvent]) -> None:
        for event in events:
            self.dispatch(event)
