"""适配器：将 INotificationGateway 适配为 IRiskNotifier，解决两套通知接口不兼容问题。"""

from src.domain.notification.interfaces.notification_gateway import INotificationGateway
from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)
from src.domain.risk.interfaces.notification import IRiskNotifier
from src.domain.risk.value_objects.risk_event import RiskEvent, RiskEventType, RiskSeverity


class RiskNotifierAdapter(INotificationGateway):
    """将 IRiskNotifier 适配为 INotificationGateway。

    允许 AutoPauseManager 等使用 INotificationGateway 接口的代码
    通过 RiskEventDispatcher 派发通知。
    """

    _SEVERITY_MAP: dict[RiskSeverity, NotificationLevel] = {
        RiskSeverity.INFO: NotificationLevel.INFO,
        RiskSeverity.WARNING: NotificationLevel.WARNING,
        RiskSeverity.CRITICAL: NotificationLevel.CRITICAL,
    }

    def __init__(self, notifier: IRiskNotifier) -> None:
        self._notifier = notifier

    def send(self, message: NotificationMessage) -> bool:
        """将 NotificationMessage 转换为 RiskEvent 并通过 IRiskNotifier 发送。"""
        severity = {
            NotificationLevel.INFO: RiskSeverity.INFO,
            NotificationLevel.WARNING: RiskSeverity.WARNING,
            NotificationLevel.CRITICAL: RiskSeverity.CRITICAL,
            NotificationLevel.EMERGENCY: RiskSeverity.CRITICAL,
        }.get(message.level, RiskSeverity.INFO)

        # 尝试将 category 映射到 RiskEventType，未知则用 ANOMALY_DETECTED
        cat_upper = message.category.upper()
        event_type = RiskEventType.ANOMALY_DETECTED
        for rt in RiskEventType:
            if rt.value == cat_upper:
                event_type = rt
                break

        event = RiskEvent(
            event_type=event_type,
            severity=severity,
            message=f"{message.title}: {message.body}",
            timestamp=message.timestamp,
            metadata=dict(message.metadata),
        )
        self._notifier.notify(event)
        return True

    def send_batch(self, messages: list[NotificationMessage]) -> int:
        """批量发送通知。"""
        success = 0
        for msg in messages:
            if self.send(msg):
                success += 1
        return success
