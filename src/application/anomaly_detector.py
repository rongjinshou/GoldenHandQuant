import logging

from src.application.auto_pause_manager import AutoPauseManager
from src.domain.notification.interfaces.notification_gateway import INotificationGateway
from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)
from src.domain.risk.services.anomaly_detectors.base import BaseAnomalyDetector
from src.domain.risk.value_objects.anomaly_event import (
    AnomalyEvent,
    AutoAction,
)

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """异常检测聚合器。

    聚合多个子检测器，统一输出异常事件，并触发自动暂停。
    """

    def __init__(
        self,
        strategy_detectors: list[BaseAnomalyDetector] | None = None,
        data_detectors: list[BaseAnomalyDetector] | None = None,
        market_detectors: list[BaseAnomalyDetector] | None = None,
        ml_detectors: list[BaseAnomalyDetector] | None = None,
        pause_manager: AutoPauseManager | None = None,
        notification_gateway: INotificationGateway | None = None,
    ) -> None:
        self._detectors: list[BaseAnomalyDetector] = []
        if strategy_detectors:
            self._detectors.extend(strategy_detectors)
        if data_detectors:
            self._detectors.extend(data_detectors)
        if market_detectors:
            self._detectors.extend(market_detectors)
        if ml_detectors:
            self._detectors.extend(ml_detectors)
        self._pause_manager = pause_manager
        self._notification_gateway = notification_gateway

    def run_checks(self) -> list[AnomalyEvent]:
        """运行所有异常检测。

        Returns:
            检测到的异常事件列表。
        """
        events: list[AnomalyEvent] = []
        for detector in self._detectors:
            try:
                detected = detector.detect()
                events.extend(detected)
            except Exception as e:
                logger.error("异常检测器执行失败: %s", e, exc_info=True)

        # 根据严重程度决定是否自动暂停
        for event in events:
            self._handle_event(event)

        return events

    def _handle_event(self, event: AnomalyEvent) -> None:
        """处理单个异常事件。"""
        logger.warning("异常检测: [%s] %s", event.severity, event.message)

        # 推送通知
        if self._notification_gateway:
            level = (
                NotificationLevel.CRITICAL
                if event.severity.value == "critical"
                else NotificationLevel.WARNING
            )
            msg = NotificationMessage(
                title=f"异常检测: {event.anomaly_type.value}",
                body=event.message,
                level=level,
                category="anomaly",
            )
            try:
                self._notification_gateway.send(msg)
            except Exception as e:
                logger.error("异常通知发送失败: %s", e)

        # 自动暂停
        if not self._pause_manager:
            return
        if event.auto_action == AutoAction.PAUSE_ALL:
            self._pause_manager.pause_all(event)
        elif event.auto_action == AutoAction.PAUSE_STRATEGY:
            self._pause_manager.pause_strategy(event.source, event)
