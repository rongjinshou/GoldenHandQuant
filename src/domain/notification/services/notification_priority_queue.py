"""通知优先级队列。

根据通知优先级决定发送策略：
- EMERGENCY / CRITICAL: 立即发送
- WARNING: 进入队列按序发送
- INFO: 批量合并后发送
"""


from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)
from src.domain.notification.value_objects.notification_priority import (
    NotificationPriority,
)


class NotificationPriorityQueue:
    """通知优先级队列。

    纯领域服务，管理不同优先级通知的排队与批量策略。
    不直接发送通知，而是由调用方（如 NotificationHub）根据返回的策略执行发送。
    """

    def __init__(self, batch_size: int = 10) -> None:
        """
        Args:
            batch_size: INFO 级别批量合并的阈值。
        """
        self._batch_size = batch_size
        self._warning_queue: list[NotificationMessage] = []
        self._info_buffer: list[NotificationMessage] = []

    @staticmethod
    def classify(message: NotificationMessage) -> NotificationPriority:
        """根据消息级别映射到优先级。

        Args:
            message: 通知消息。

        Returns:
            对应的优先级。
        """
        mapping = {
            NotificationLevel.EMERGENCY: NotificationPriority.EMERGENCY,
            NotificationLevel.CRITICAL: NotificationPriority.CRITICAL,
            NotificationLevel.WARNING: NotificationPriority.WARNING,
            NotificationLevel.INFO: NotificationPriority.INFO,
        }
        return mapping[message.level]

    def enqueue(self, message: NotificationMessage) -> "EnqueueResult":
        """将消息加入队列，返回发送策略。

        Args:
            message: 通知消息。

        Returns:
            EnqueueResult 描述应如何处理该消息。
        """
        priority = self.classify(message)

        if priority in (NotificationPriority.EMERGENCY, NotificationPriority.CRITICAL):
            return EnqueueResult(
                action=SendAction.SEND_IMMEDIATELY,
                messages=[message],
            )

        if priority == NotificationPriority.WARNING:
            self._warning_queue.append(message)
            return EnqueueResult(
                action=SendAction.QUEUED,
                messages=[],
            )

        # INFO: 批量合并
        self._info_buffer.append(message)
        if len(self._info_buffer) >= self._batch_size:
            batch = list(self._info_buffer)
            self._info_buffer.clear()
            return EnqueueResult(
                action=SendAction.SEND_BATCH,
                messages=batch,
            )

        return EnqueueResult(
            action=SendAction.BUFFERED,
            messages=[],
        )

    def flush_warnings(self) -> list[NotificationMessage]:
        """取出所有排队的 WARNING 消息并清空队列。

        Returns:
            WARNING 消息列表。
        """
        messages = list(self._warning_queue)
        self._warning_queue.clear()
        return messages

    def flush_info_buffer(self) -> list[NotificationMessage]:
        """取出所有缓存的 INFO 消息并清空缓冲区。

        Returns:
            INFO 消息列表。
        """
        messages = list(self._info_buffer)
        self._info_buffer.clear()
        return messages

    @property
    def pending_warning_count(self) -> int:
        """队列中等待发送的 WARNING 消息数量。"""
        return len(self._warning_queue)

    @property
    def buffered_info_count(self) -> int:
        """缓冲区中等待合并的 INFO 消息数量。"""
        return len(self._info_buffer)


class SendAction:
    """发送动作常量。"""

    SEND_IMMEDIATELY = "send_immediately"
    QUEUED = "queued"
    SEND_BATCH = "send_batch"
    BUFFERED = "buffered"


class EnqueueResult:
    """入队结果，描述消息应如何被处理。"""

    __slots__ = ("action", "messages")

    def __init__(self, action: str, messages: list[NotificationMessage]) -> None:
        self.action = action
        self.messages = messages

    def __repr__(self) -> str:
        return f"EnqueueResult(action={self.action!r}, count={len(self.messages)})"
