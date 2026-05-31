import logging
from datetime import datetime

from src.domain.notification.interfaces.notification_gateway import INotificationGateway
from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)
from src.domain.trade.value_objects.execution_record import ExecutionRecord
from src.domain.trade.value_objects.execution_stats import ExecutionStats
from src.domain.trade.value_objects.execution_status import ExecutionStatus

logger = logging.getLogger(__name__)


def _volume_level(volume: int) -> str:
    """将精确数量转换为模糊级别（如 1000 -> '1K 级'）。"""
    if volume < 100:
        return "<100"
    if volume < 1000:
        return "100 级"
    if volume < 5000:
        return "1K 级"
    if volume < 10000:
        return "5K 级"
    if volume < 50000:
        return "1W 级"
    return ">5W"


class RateLimiter:
    """频率限制器。"""

    def __init__(self, max_per_minute: int = 10) -> None:
        self._max_per_minute = max_per_minute
        self._timestamps: list[datetime] = []

    def allow(self) -> bool:
        """检查是否允许发送。"""
        now = datetime.now()
        cutoff = now.timestamp() - 60
        self._timestamps = [t for t in self._timestamps if t.timestamp() > cutoff]
        if len(self._timestamps) >= self._max_per_minute:
            return False
        self._timestamps.append(now)
        return True


class NotificationHub:
    """通知中心。

    聚合系统内所有事件源，路由到对应的通知渠道。
    支持频率限制、静默时段。
    """

    def __init__(
        self,
        gateways: list[INotificationGateway],
        rate_limiter: RateLimiter | None = None,
        quiet_hours: tuple[int, int] | None = None,
    ) -> None:
        self._gateways = gateways
        self._rate_limiter = rate_limiter or RateLimiter()
        self._quiet_hours = quiet_hours  # (start_hour, end_hour)

    def notify(self, message: NotificationMessage) -> None:
        """发送通知到所有渠道。"""
        # 紧急消息不受静默时段限制
        if message.level != NotificationLevel.EMERGENCY:
            if self._is_quiet_hour():
                logger.debug("静默时段，跳过通知: %s", message.title)
                return

        if not self._rate_limiter.allow():
            logger.warning("通知频率超限，跳过: %s", message.title)
            return

        for gateway in self._gateways:
            try:
                gateway.send(message)
            except Exception as e:
                logger.error("通知发送失败: %s - %s", message.title, e)

    def notify_trade_executed(
        self, record: ExecutionRecord, *, sanitize: bool = True,
    ) -> None:
        """交易执行通知。

        Args:
            record: 执行记录。
            sanitize: 是否对敏感信息脱敏（价格只保留整数，数量显示级别）。
        """
        status_text = "成功" if record.status == ExecutionStatus.FILLED else record.status.value
        level = NotificationLevel.INFO
        if record.status in (ExecutionStatus.FAILED, ExecutionStatus.REJECTED):
            level = NotificationLevel.WARNING

        if sanitize:
            price_text = f"价格: {int(record.target_price)}\n"
            volume_text = f"数量: {_volume_level(record.target_volume)}\n"
        else:
            price_text = f"价格: {record.target_price:.2f}\n"
            volume_text = f"数量: {record.target_volume}\n"

        self.notify(NotificationMessage(
            title=f"交易执行: {record.symbol}",
            body=(
                f"方向: {record.direction.value}\n"
                f"{price_text}"
                f"{volume_text}"
                f"状态: {status_text}"
            ),
            level=level,
            category="trade",
        ))

    def notify_anomaly_detected(self, event) -> None:
        """异常检测通知。"""
        from src.domain.risk.value_objects.anomaly_event import AnomalySeverity
        level = (
            NotificationLevel.CRITICAL
            if event.severity == AnomalySeverity.CRITICAL
            else NotificationLevel.WARNING
        )
        self.notify(NotificationMessage(
            title=f"异常检测: {event.anomaly_type.value}",
            body=event.message,
            level=level,
            category="anomaly",
        ))

    def notify_daily_report(self, stats: ExecutionStats) -> None:
        """每日报告通知。"""
        self.notify(NotificationMessage(
            title="每日执行报告",
            body=(
                f"总订单: {stats.total_orders}\n"
                f"成功: {stats.successful_orders}\n"
                f"失败: {stats.failed_orders}\n"
                f"成功率: {stats.success_rate:.1%}\n"
                f"买入滑点: {stats.avg_slippage_buy:.3%}\n"
                f"卖出滑点: {stats.avg_slippage_sell:.3%}"
            ),
            level=NotificationLevel.INFO,
            category="system",
        ))

    def _is_quiet_hour(self) -> bool:
        """检查当前是否在静默时段。"""
        if not self._quiet_hours:
            return False
        now_hour = datetime.now().hour
        start, end = self._quiet_hours
        if start <= end:
            return start <= now_hour < end
        else:
            return now_hour >= start or now_hour < end
