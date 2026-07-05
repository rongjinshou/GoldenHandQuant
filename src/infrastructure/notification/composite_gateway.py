"""组合通知网关 — 将多条 INotificationGateway 合并为一个，广播到所有渠道。

解决债 TD-03: factory.py 原来只取 notifiers[0]，多渠道配置时其余渠道被静默丢弃。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from src.domain.notification.interfaces.notification_gateway import INotificationGateway
from src.domain.notification.value_objects.notification_message import NotificationMessage

logger = logging.getLogger(__name__)


class CompositeNotificationGateway:
    """将多条 INotificationGateway 合并为一个网关。

    发送时广播到所有底层网关；任意一条失败不阻塞其余。
    """

    def __init__(self, gateways: Sequence[INotificationGateway]) -> None:
        if not gateways:
            raise ValueError("CompositeNotificationGateway 至少需要一个底层网关")
        self._gateways = list(gateways)

    def send(self, message: NotificationMessage) -> bool:
        success = False
        for gw in self._gateways:
            try:
                if gw.send(message):
                    success = True
            except Exception as e:
                logger.warning("通知渠道 %s 发送失败: %s", type(gw).__name__, e)
        return success

    def send_batch(self, messages: list[NotificationMessage]) -> int:
        total = 0
        for gw in self._gateways:
            try:
                total += gw.send_batch(messages)
            except Exception as e:
                logger.warning("通知渠道 %s 批量发送失败: %s", type(gw).__name__, e)
        return total
