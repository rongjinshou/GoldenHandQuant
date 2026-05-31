"""交易编排器（应用层）。

从 AutoTradingEngine 中抽取的业务编排逻辑。
职责：信号生成 → 管线处理 → 下单 → 执行记录 → 通知。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.application.anomaly_detector import AnomalyDetector
from src.application.auto_pause_manager import AutoPauseManager
from src.application.notification_hub import NotificationHub
from src.application.order_executor import OrderExecutor
from src.application.signal_pipeline import SignalPipeline
from src.application.strategy_runner import DayContext, StrategyRunner
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.trade.services.execution_monitor import ExecutionMonitor
from src.domain.trade.value_objects.execution_record import ExecutionRecord

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class CycleResult:
    """单次交易循环结果。"""
    cycle_time: datetime
    signals_generated: int
    orders_placed: int
    orders_rejected: int
    orders_failed: int
    anomaly_events: int
    records: list[ExecutionRecord] = field(default_factory=list)


class TradingOrchestrator:
    """交易业务编排器。

    负责一次完整交易循环的核心流程：
    信号生成 → 信号管线处理 → 下单执行 → 记录 → 通知。
    """

    def __init__(
        self,
        strategy_runners: list[StrategyRunner],
        signal_pipeline: SignalPipeline,
        order_executor: OrderExecutor,
        execution_monitor: ExecutionMonitor,
        anomaly_detector: AnomalyDetector,
        notification_hub: NotificationHub | None = None,
        max_orders_per_cycle: int = 20,
        symbols: list[str] | None = None,
        pause_manager: AutoPauseManager | None = None,
    ) -> None:
        self._strategy_runners = strategy_runners
        self._signal_pipeline = signal_pipeline
        self._order_executor = order_executor
        self._execution_monitor = execution_monitor
        self._anomaly_detector = anomaly_detector
        self._notification_hub = notification_hub
        self._max_orders_per_cycle = max_orders_per_cycle
        self._symbols = symbols or []
        self._pause_manager = pause_manager

    def execute_cycle(self, now: datetime) -> CycleResult:
        """执行一次完整的交易循环。

        Args:
            now: 当前时间。

        Returns:
            本次循环结果。
        """
        # 1. 异常检测前置检查
        anomaly_events = self._anomaly_detector.run_checks()

        # 2. 逐策略生成信号
        all_signals: list[Signal] = []
        prices: dict[str, float] = {}
        for runner in self._strategy_runners:
            strategy_obj = getattr(runner, "strategy", None)
            strategy_name = (
                getattr(runner, "strategy_name", None)
                or getattr(strategy_obj, "name", None)
            )
            if self._pause_manager and strategy_name and self._pause_manager.is_strategy_paused(strategy_name):
                logger.info("策略 %s 已暂停，跳过", strategy_name)
                continue

            context = DayContext(
                current_time=now,
                symbols=self._symbols,
                base_timeframe=Timeframe.DAY_1,
            )
            try:
                runner_targets, runner_prices = runner.evaluate(context)
                prices.update(runner_prices)
                for target in runner_targets:
                    all_signals.append(Signal(
                        symbol=target.symbol,
                        direction=SignalDirection(target.direction.value),
                        confidence_score=1.0,
                        strategy_name=target.strategy_name,
                    ))
            except Exception as e:
                logger.error("策略执行失败: %s", e, exc_info=True)

        # 3. 全局熔断检查
        if self._pause_manager and self._pause_manager.is_all_paused:
            logger.warning("全局暂停中，跳过本周期下单")
            return CycleResult(
                cycle_time=now,
                signals_generated=len(all_signals),
                orders_placed=0,
                orders_rejected=0,
                orders_failed=0,
                anomaly_events=len(anomaly_events),
            )

        # 4. 信号管线处理
        targets = self._signal_pipeline.process(all_signals, prices)

        # 限制单次循环最大下单数
        if len(targets) > self._max_orders_per_cycle:
            logger.warning(
                "信号数 (%d) 超过上限 (%d)，截断",
                len(targets), self._max_orders_per_cycle,
            )
            targets = targets[:self._max_orders_per_cycle]

        # 5. 自动下单
        records = self._order_executor.execute(targets)

        # 6. 记录执行结果
        for record in records:
            self._execution_monitor.record(record)

        placed = sum(1 for r in records if r.status.value == "submitted")
        rejected = sum(1 for r in records if r.status.value == "rejected")
        failed = sum(1 for r in records if r.status.value == "failed")

        result = CycleResult(
            cycle_time=now,
            signals_generated=len(all_signals),
            orders_placed=placed,
            orders_rejected=rejected,
            orders_failed=failed,
            anomaly_events=len(anomaly_events),
            records=records,
        )

        # 7. 推送通知
        if self._notification_hub and records:
            for record in records:
                self._notification_hub.notify_trade_executed(record)

        logger.info(
            "交易循环完成: 信号=%d, 下单=%d, 拒绝=%d, 失败=%d, 异常=%d",
            len(all_signals), placed, rejected, failed, len(anomaly_events),
        )

        return result
