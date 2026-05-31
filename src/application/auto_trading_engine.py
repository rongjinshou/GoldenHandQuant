import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.application.anomaly_detector import AnomalyDetector
from src.application.auto_pause_manager import AutoPauseManager
from src.application.notification_hub import NotificationHub
from src.application.order_executor import OrderExecutor
from src.application.signal_pipeline import SignalPipeline
from src.application.strategy_runner import StrategyRunner
from src.application.trading_orchestrator import CycleResult, TradingOrchestrator
from src.application.trading_scheduler import TradingScheduler
from src.domain.trade.services.execution_monitor import ExecutionMonitor

logger = logging.getLogger(__name__)

# 向后兼容：CycleResult 现在定义在 trading_orchestrator 中
__all__ = ["AutoTradingConfig", "AutoTradingEngine", "CycleResult"]


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


class AutoTradingEngine:
    """全自动交易引擎（门面）。

    组合 TradingScheduler（调度）+ TradingOrchestrator（编排），
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
        self._config = config or AutoTradingConfig()

        # 编排器：业务逻辑
        self._orchestrator = TradingOrchestrator(
            strategy_runners=strategy_runners,
            signal_pipeline=signal_pipeline,
            order_executor=order_executor,
            execution_monitor=execution_monitor,
            anomaly_detector=anomaly_detector,
            notification_hub=notification_hub,
            max_orders_per_cycle=self._config.max_orders_per_cycle,
            symbols=self._config.symbols,
            pause_manager=pause_manager,
        )

        # 调度器：线程管理、时间判断
        self._scheduler = TradingScheduler(
            check_interval_seconds=self._config.check_interval_seconds,
            execution_times=self._config.execution_times,
        )
        self._scheduler.register_cycle_callback(self._on_cycle)

        # 向后兼容属性
        self._running = self._scheduler._running
        self._cycle_results: list[CycleResult] = []
        self._config_obj = self._config

    @property
    def is_running(self) -> bool:
        return self._scheduler.is_running

    @property
    def config(self) -> AutoTradingConfig:
        return self._config

    def run_cycle(self, current_time: datetime | None = None) -> CycleResult:
        """执行一次完整的自动交易循环。"""
        now = current_time or datetime.now()

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

        result = self._orchestrator.execute_cycle(now)
        self._cycle_results.append(result)
        return result

    def start(self) -> None:
        """启动自动交易循环 (守护线程)。"""
        if not self._config.enabled:
            logger.warning("自动交易未启用，无法启动")
            return
        self._scheduler.start()

    def stop(self) -> None:
        """停止自动交易。"""
        self._scheduler.stop()
        logger.info("自动交易引擎已停止")

    def get_cycle_results(self) -> list[CycleResult]:
        """获取所有循环结果。"""
        return list(self._cycle_results)

    def _on_cycle(self, now: datetime) -> None:
        """调度器回调：执行一次循环。"""
        self.run_cycle(now)

    # 向后兼容方法（测试中使用）
    def _is_trading_hour(self, now: datetime) -> bool:
        return self._scheduler._is_trading_hour(now)

    def _should_execute(self, now: datetime) -> bool:
        return self._scheduler._should_execute(now)
