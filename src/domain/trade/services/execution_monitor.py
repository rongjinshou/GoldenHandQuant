import logging
from datetime import datetime

from src.domain.trade.value_objects.execution_record import ExecutionRecord
from src.domain.trade.value_objects.execution_stats import ExecutionStats
from src.domain.trade.value_objects.execution_status import ExecutionStatus
from src.domain.trade.value_objects.health_status import HealthStatus
from src.domain.trade.value_objects.order_direction import OrderDirection

logger = logging.getLogger(__name__)


class ExecutionMonitor:
    """执行质量监控。

    职责:
    - 记录每次执行结果
    - 统计成功率、滑点
    - 检查执行健康状态
    """

    def __init__(self) -> None:
        self._records: list[ExecutionRecord] = []

    def record(self, record: ExecutionRecord) -> None:
        """记录一次执行结果。"""
        self._records.append(record)

    def get_records(self, days: int = 30) -> list[ExecutionRecord]:
        """获取最近 N 天的执行记录。"""
        cutoff = datetime.now()
        from datetime import timedelta
        cutoff = cutoff - timedelta(days=days)
        return [r for r in self._records if r.submitted_at >= cutoff]

    def get_stats(self, days: int = 30) -> ExecutionStats:
        """获取最近 N 天的执行统计。"""
        records = self.get_records(days)
        if not records:
            return ExecutionStats(
                total_orders=0,
                successful_orders=0,
                failed_orders=0,
                success_rate=0.0,
                avg_slippage_buy=0.0,
                avg_slippage_sell=0.0,
                max_slippage=0.0,
                avg_fill_time_seconds=0.0,
            )

        total = len(records)
        successful = sum(
            1 for r in records if r.status == ExecutionStatus.FILLED
        )
        failed = sum(
            1 for r in records
            if r.status in (ExecutionStatus.FAILED, ExecutionStatus.REJECTED)
        )

        buy_slippages = [
            abs(r.slippage) for r in records
            if r.direction == OrderDirection.BUY and r.status == ExecutionStatus.FILLED
        ]
        sell_slippages = [
            abs(r.slippage) for r in records
            if r.direction == OrderDirection.SELL and r.status == ExecutionStatus.FILLED
        ]

        all_slippages = [abs(r.slippage) for r in records if r.status == ExecutionStatus.FILLED]

        fill_times: list[float] = []
        for r in records:
            if r.filled_at and r.status == ExecutionStatus.FILLED:
                delta = (r.filled_at - r.submitted_at).total_seconds()
                fill_times.append(delta)

        return ExecutionStats(
            total_orders=total,
            successful_orders=successful,
            failed_orders=failed,
            success_rate=successful / total if total > 0 else 0.0,
            avg_slippage_buy=sum(buy_slippages) / len(buy_slippages) if buy_slippages else 0.0,
            avg_slippage_sell=sum(sell_slippages) / len(sell_slippages) if sell_slippages else 0.0,
            max_slippage=max(all_slippages) if all_slippages else 0.0,
            avg_fill_time_seconds=sum(fill_times) / len(fill_times) if fill_times else 0.0,
        )

    def check_health(self, days: int = 30) -> HealthStatus:
        """检查执行健康状态。

        规则:
        - 成功率 < 90% -> WARNING
        - 成功率 < 80% -> CRITICAL
        - 平均滑点 > 0.3% -> WARNING
        - 平均滑点 > 0.5% -> CRITICAL
        """
        stats = self.get_stats(days)
        if stats.total_orders == 0:
            return HealthStatus.HEALTHY

        if stats.success_rate < 0.80:
            return HealthStatus.CRITICAL
        if stats.success_rate < 0.90:
            return HealthStatus.WARNING

        avg_slippage = (
            stats.avg_slippage_buy + stats.avg_slippage_sell
        ) / 2
        if avg_slippage > 0.005:
            return HealthStatus.CRITICAL
        if avg_slippage > 0.003:
            return HealthStatus.WARNING

        return HealthStatus.HEALTHY

    def clear(self) -> None:
        """清空所有记录。"""
        self._records.clear()
