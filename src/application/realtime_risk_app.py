"""实时风控应用服务。

集成到 AutoTradingEngine.run_cycle()，盘中持续监控。
异常时自动暂停交易。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.application.anomaly_detector import AnomalyDetector
from src.application.auto_pause_manager import AutoPauseManager
from src.application.notification_hub import NotificationHub
from src.domain.risk.services.realtime_risk_monitor import RealtimeRiskMonitor, TickData
from src.domain.risk.services.realtime_stop_loss import (
    RealtimeStopLossService,
    StopLossTrigger,
)
from src.domain.risk.value_objects.risk_alert import (
    RiskAlert,
    RiskAlertSeverity,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class RealtimeRiskCheckResult:
    """实时风控检查结果。"""
    timestamp: datetime
    alerts: list[RiskAlert] = field(default_factory=list)
    stop_triggers: list[StopLossTrigger] = field(default_factory=list)
    trading_paused: bool = False
    pause_reason: str = ""


class RealtimeRiskAppService:
    """实时风控应用服务。

    职责：
    1. 接收 Tick 数据，驱动风控监控和止损检查
    2. 根据告警严重程度决定是否暂停交易
    3. 推送通知

    集成方式：
    - 在 AutoTradingEngine.run_cycle() 中调用 check_tick()
    - 或在独立的高频监控循环中调用
    """

    def __init__(
        self,
        risk_monitor: RealtimeRiskMonitor | None = None,
        stop_loss_service: RealtimeStopLossService | None = None,
        anomaly_detector: AnomalyDetector | None = None,
        pause_manager: AutoPauseManager | None = None,
        notification_hub: NotificationHub | None = None,
        auto_pause_on_critical: bool = True,
    ) -> None:
        self._risk_monitor = risk_monitor or RealtimeRiskMonitor()
        self._stop_loss_service = stop_loss_service or RealtimeStopLossService()
        self._anomaly_detector = anomaly_detector
        self._pause_manager = pause_manager
        self._notification_hub = notification_hub
        self._auto_pause_on_critical = auto_pause_on_critical

        self._check_history: list[RealtimeRiskCheckResult] = []
        self._paused: bool = False
        self._paused_reason: str = ""

    @property
    def is_paused(self) -> bool:
        """风控是否已暂停交易。"""
        return self._paused

    @property
    def paused_reason(self) -> str:
        """暂停原因。"""
        return self._paused_reason

    @property
    def risk_monitor(self) -> RealtimeRiskMonitor:
        """风控监控器（用于外部配置）。"""
        return self._risk_monitor

    @property
    def stop_loss_service(self) -> RealtimeStopLossService:
        """止损服务（用于外部配置止损规则）。"""
        return self._stop_loss_service

    def check_tick(self, tick: TickData) -> RealtimeRiskCheckResult:
        """处理单个 Tick，执行全部风控检查。

        Args:
            tick: Tick 行情数据。

        Returns:
            风控检查结果。
        """
        all_alerts: list[RiskAlert] = []

        # 1. 价格异常监控（on_tick 已直接返回本轮告警）
        monitor_alerts = self._risk_monitor.on_tick(tick)
        all_alerts.extend(monitor_alerts)

        # 2. 止损检查
        trigger = self._stop_loss_service.on_price_update(
            tick.symbol, tick.price, tick.timestamp,
        )
        stop_triggers: list[StopLossTrigger] = []
        if trigger:
            stop_triggers.append(trigger)
            all_alerts.extend(self._stop_loss_service.collect_alerts())

        # 4. 判断是否需要暂停
        trading_paused = False
        pause_reason = ""
        if self._auto_pause_on_critical:
            critical_alerts = [a for a in all_alerts if a.severity == RiskAlertSeverity.CRITICAL]
            if critical_alerts:
                trading_paused = True
                pause_reason = critical_alerts[0].message
                self._paused = True
                self._paused_reason = pause_reason

                # 通知暂停管理器
                if self._pause_manager:
                    from src.domain.risk.value_objects.anomaly_event import (
                        AnomalyEvent,
                        AnomalySeverity,
                        AnomalyType,
                        AutoAction,
                    )
                    event = AnomalyEvent(
                        anomaly_type=AnomalyType.MARKET,
                        severity=AnomalySeverity.CRITICAL,
                        source="realtime_risk",
                        message=pause_reason,
                        metric_value=0.0,
                        threshold=0.0,
                        auto_action=AutoAction.PAUSE_ALL,
                    )
                    self._pause_manager.pause_all(event)

        # 5. 推送通知
        if self._notification_hub and all_alerts:
            self._send_notifications(all_alerts)

        # 6. 记录结果
        result = RealtimeRiskCheckResult(
            timestamp=tick.timestamp,
            alerts=all_alerts,
            stop_triggers=stop_triggers,
            trading_paused=trading_paused,
            pause_reason=pause_reason,
        )
        self._check_history.append(result)

        return result

    def check_ticks(self, ticks: list[TickData]) -> RealtimeRiskCheckResult:
        """批量处理 Tick 数据。

        Args:
            ticks: Tick 数据列表。

        Returns:
            合并后的风控检查结果。
        """
        all_alerts: list[RiskAlert] = []
        all_triggers: list[StopLossTrigger] = []
        trading_paused = False
        pause_reason = ""

        for tick in ticks:
            result = self.check_tick(tick)
            all_alerts.extend(result.alerts)
            all_triggers.extend(result.stop_triggers)
            if result.trading_paused and not trading_paused:
                trading_paused = True
                pause_reason = result.pause_reason

        return RealtimeRiskCheckResult(
            timestamp=ticks[-1].timestamp if ticks else datetime.now(),
            alerts=all_alerts,
            stop_triggers=all_triggers,
            trading_paused=trading_paused,
            pause_reason=pause_reason,
        )

    def resume(self) -> None:
        """恢复交易。"""
        self._paused = False
        self._paused_reason = ""
        logger.info("实时风控已恢复交易")

    def get_check_history(self) -> list[RealtimeRiskCheckResult]:
        """获取检查历史。"""
        return list(self._check_history)

    def _send_notifications(self, alerts: list[RiskAlert]) -> None:
        """推送告警通知。"""
        from src.domain.notification.value_objects.notification_message import (
            NotificationLevel,
            NotificationMessage,
        )

        for alert in alerts:
            level = (
                NotificationLevel.CRITICAL
                if alert.severity == RiskAlertSeverity.CRITICAL
                else NotificationLevel.WARNING
            )
            msg = NotificationMessage(
                title=f"实时风控 [{alert.alert_type.value}]",
                body=alert.message,
                level=level,
                category="realtime_risk",
            )
            try:
                self._notification_hub.send(msg)
            except Exception as e:
                logger.error("风控通知发送失败: %s", e)
