import logging
import threading
import time as time_mod
from dataclasses import dataclass, field
from datetime import datetime, time

from src.application.anomaly_detector import AnomalyDetector
from src.application.auto_pause_manager import AutoPauseManager
from src.application.notification_hub import NotificationHub
from src.application.order_executor import OrderExecutor
from src.application.signal_pipeline import SignalPipeline
from src.application.strategy_runner import DayContext, StrategyRunner
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.value_objects.signal import Signal
from src.domain.trade.services.execution_monitor import ExecutionMonitor
from src.domain.trade.value_objects.execution_record import ExecutionRecord

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class AutoTradingConfig:
    """自动交易配置。"""
    strategy_names: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    execution_times: list[str] = field(default_factory=lambda: ["09:35", "14:50"])
    max_orders_per_cycle: int = 20
    min_confidence: float = 0.6
    enabled: bool = False  # 默认关闭
    check_interval_seconds: int = 60


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


class AutoTradingEngine:
    """全自动交易引擎。

    定时执行策略信号 -> 风控检查 -> 自动下单 -> 成交跟踪。
    """

    def __init__(
        self,
        strategy_runners: list[StrategyRunner],
        signal_pipeline: SignalPipeline,
        order_executor: OrderExecutor,
        execution_monitor: ExecutionMonitor,
        anomaly_detector: AnomalyDetector,
        notification_hub: NotificationHub | None = None,
        config: AutoTradingConfig | None = None,
        pause_manager: AutoPauseManager | None = None,
    ) -> None:
        self._strategy_runners = strategy_runners
        self._signal_pipeline = signal_pipeline
        self._order_executor = order_executor
        self._execution_monitor = execution_monitor
        self._anomaly_detector = anomaly_detector
        self._notification_hub = notification_hub
        self._config = config or AutoTradingConfig()
        self._pause_manager = pause_manager

        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._cycle_results: list[CycleResult] = []

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    @property
    def config(self) -> AutoTradingConfig:
        return self._config

    def run_cycle(self, current_time: datetime | None = None) -> CycleResult:
        """执行一次完整的自动交易循环。"""
        now = current_time or datetime.now()

        # 0. 检查是否启用
        if not self._config.enabled:
            logger.info("自动交易未启用，跳过循环")
            return CycleResult(
                cycle_time=now,
                signals_generated=0,
                orders_placed=0,
                orders_rejected=0,
                orders_failed=0,
                anomaly_events=0,
            )

        # 1. 异常检测前置检查
        anomaly_events = self._anomaly_detector.run_checks()

        # 2. 生成信号
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
                symbols=self._config.symbols,
                base_timeframe=Timeframe.DAY_1,
            )
            try:
                runner_targets, runner_prices = runner.evaluate(context)
                prices.update(runner_prices)
                # Convert targets back to signals for pipeline processing
                for target in runner_targets:
                    from src.domain.strategy.value_objects.signal_direction import SignalDirection
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
        if len(targets) > self._config.max_orders_per_cycle:
            logger.warning(
                "信号数 (%d) 超过上限 (%d)，截断",
                len(targets), self._config.max_orders_per_cycle,
            )
            targets = targets[:self._config.max_orders_per_cycle]

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
        self._cycle_results.append(result)

        # 7. 推送通知
        if self._notification_hub and records:
            for record in records:
                self._notification_hub.notify_trade_executed(record)

        logger.info(
            "交易循环完成: 信号=%d, 下单=%d, 拒绝=%d, 失败=%d, 异常=%d",
            len(all_signals), placed, rejected, failed, len(anomaly_events),
        )

        return result

    def start(self) -> None:
        """启动自动交易循环 (守护线程)。"""
        if self._running.is_set():
            logger.warning("自动交易已在运行")
            return
        if not self._config.enabled:
            logger.warning("自动交易未启用，无法启动")
            return

        self._running.set()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("自动交易引擎已启动")

    def stop(self) -> None:
        """停止自动交易。"""
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=30)
            self._thread = None
        logger.info("自动交易引擎已停止")

    def get_cycle_results(self) -> list[CycleResult]:
        """获取所有循环结果。"""
        return list(self._cycle_results)

    def _run_loop(self) -> None:
        """主循环: 每分钟检查是否到达执行时间。"""
        while self._running.is_set():
            now = datetime.now()
            if self._is_trading_hour(now) and self._should_execute(now):
                try:
                    self.run_cycle(now)
                except Exception as e:
                    logger.error("交易循环异常: %s", e, exc_info=True)
            time_mod.sleep(self._config.check_interval_seconds)

    def _is_trading_hour(self, now: datetime) -> bool:
        """检查是否在交易时段内。"""
        t = now.time()
        morning = time(9, 25) <= t <= time(11, 30)
        afternoon = time(13, 0) <= t <= time(15, 0)
        return morning or afternoon

    def _should_execute(self, now: datetime) -> bool:
        """检查当前时间是否匹配执行时间。"""
        current_str = now.strftime("%H:%M")
        return current_str in self._config.execution_times
