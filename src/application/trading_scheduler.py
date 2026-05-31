"""交易调度器（应用层）。

从 AutoTradingEngine 中抽取的调度逻辑。
职责：线程管理、时间判断、心跳、异常捕获。
"""

import logging
import threading
import time as time_mod
from collections.abc import Callable
from datetime import datetime, time

logger = logging.getLogger(__name__)


class TradingScheduler:
    """交易调度器。

    管理守护线程生命周期、心跳机制、交易时段判断。
    """

    def __init__(
        self,
        check_interval_seconds: int = 60,
        execution_times: list[str] | None = None,
    ) -> None:
        self._check_interval_seconds = check_interval_seconds
        self._execution_times = set(execution_times or ["09:35", "14:50"])
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._on_cycle: Callable[[datetime], object] | None = None

    @property
    def is_running(self) -> bool:
        """是否正在运行。"""
        return self._running.is_set()

    def register_cycle_callback(self, callback: "Callable[[datetime], object]") -> None:
        """注册交易循环回调函数。

        Args:
            callback: 接收当前时间参数的回调。
        """
        self._on_cycle = callback

    def start(self) -> None:
        """启动调度线程。"""
        if self._running.is_set():
            logger.warning("调度器已在运行")
            return
        if self._on_cycle is None:
            raise RuntimeError("未注册交易循环回调，请先调用 register_cycle_callback()")

        self._running.set()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("交易调度器已启动")

    def stop(self) -> None:
        """停止调度线程。"""
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=30)
            self._thread = None
        logger.info("交易调度器已停止")

    def _run_loop(self) -> None:
        """主循环：每分钟检查是否到达执行时间。"""
        while self._running.is_set():
            now = datetime.now()
            if self._is_trading_hour(now) and self._should_execute(now):
                try:
                    if self._on_cycle:
                        self._on_cycle(now)
                except Exception as e:
                    logger.error("交易循环异常: %s", e, exc_info=True)
            time_mod.sleep(self._check_interval_seconds)

    def _is_trading_hour(self, now: datetime) -> bool:
        """检查是否在交易时段内（9:25-11:30, 13:00-15:00）。"""
        t = now.time()
        morning = time(9, 25) <= t <= time(11, 30)
        afternoon = time(13, 0) <= t <= time(15, 0)
        return morning or afternoon

    def _should_execute(self, now: datetime) -> bool:
        """检查当前时间是否匹配执行时间。"""
        current_str = now.strftime("%H:%M")
        return current_str in self._execution_times
