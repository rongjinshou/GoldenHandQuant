from typing import Protocol

from src.domain.notification.value_objects.notification_message import NotificationMessage


class INotificationGateway(Protocol):
    """通知网关接口。"""

    def send(self, message: NotificationMessage) -> bool:
        """发送单条通知。

        Returns:
            True 表示发送成功，False 表示失败。
        """
        ...

    def send_batch(self, messages: list[NotificationMessage]) -> int:
        """批量发送通知。

        Returns:
            成功发送的条数。
        """
        ...
