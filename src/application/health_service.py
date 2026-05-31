import logging
import threading
import time as time_mod
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from src.application.notification_hub import NotificationHub
from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)
from src.domain.trade.value_objects.health_status import (
    CheckResult,
    SystemHealthLevel,
    SystemHealthStatus,
)

logger = logging.getLogger(__name__)


class HealthService:
    """健康检查应用服务。

    职责:
    - Watchdog 线程监控守护线程存活
    - 心跳写入文件，供外部检测
    - 异常时自动重启 + 通知
    """

    def __init__(
        self,
        target_thread: threading.Thread,
        restart_callback: Callable[[], None] | None = None,
        notification_hub: NotificationHub | None = None,
        heartbeat_file: str | Path = "/tmp/goldenhand_healthbeat",
        heartbeat_timeout_seconds: float = 30.0,
        check_interval_seconds: float = 10.0,
    ) -> None:
        self._target = target_thread
        self._restart_callback = restart_callback
        self._notification_hub = notification_hub
        self._heartbeat_file = Path(heartbeat_file)
        self._heartbeat_timeout = heartbeat_timeout_seconds
        self._check_interval = check_interval_seconds

        self._start_time = time_mod.monotonic()
        self._last_heartbeat: datetime = datetime.now()
        self._watchdog_thread: threading.Thread | None = None
        self._running = threading.Event()
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def start(self) -> None:
        """启动 Watchdog 监控线程。"""
        if self._running.is_set():
            logger.warning("HealthService watchdog 已在运行")
            return
        self._running.set()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, daemon=True, name="health-watchdog",
        )
        self._watchdog_thread.start()
        logger.info("HealthService watchdog 已启动")

    def stop(self) -> None:
        """停止 Watchdog 监控线程。"""
        self._running.clear()
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=self._check_interval + 5)
            self._watchdog_thread = None
        logger.info("HealthService watchdog 已停止")

    def beat(self) -> None:
        """更新心跳时间并写入心跳文件。由被监控线程定期调用。"""
        with self._lock:
            self._last_heartbeat = datetime.now()
        self._write_heartbeat_file()

    def get_health_status(self) -> SystemHealthStatus:
        """获取当前系统健康状态。"""
        checks: list[CheckResult] = []
        now = datetime.now()

        # 检查目标线程是否存活
        thread_alive = self._target.is_alive()
        checks.append(CheckResult(
            name="thread_alive",
            passed=thread_alive,
            message="目标线程运行中" if thread_alive else "目标线程已停止",
            checked_at=now,
        ))

        # 检查心跳是否超时
        with self._lock:
            elapsed = (now - self._last_heartbeat).total_seconds()
        heartbeat_ok = elapsed < self._heartbeat_timeout
        checks.append(CheckResult(
            name="heartbeat",
            passed=heartbeat_ok,
            message=f"心跳正常 (间隔 {elapsed:.1f}s)"
            if heartbeat_ok
            else f"心跳超时 (间隔 {elapsed:.1f}s > {self._heartbeat_timeout}s)",
            checked_at=now,
        ))

        # 检查心跳文件
        file_exists = self._heartbeat_file.exists()
        checks.append(CheckResult(
            name="heartbeat_file",
            passed=file_exists,
            message="心跳文件存在" if file_exists else "心跳文件缺失",
            checked_at=now,
        ))

        uptime = time_mod.monotonic() - self._start_time
        return SystemHealthStatus.from_checks(
            checks=checks,
            heartbeat_time=self._last_heartbeat,
            uptime_seconds=uptime,
        )

    def _watchdog_loop(self) -> None:
        """Watchdog 主循环：定期检查健康状态，异常时触发重启和通知。"""
        while self._running.is_set():
            try:
                status = self.get_health_status()
                if not status.is_healthy:
                    self._handle_unhealthy(status)
            except Exception as e:
                logger.error("HealthService watchdog 异常: %s", e, exc_info=True)
            time_mod.sleep(self._check_interval)

    def _handle_unhealthy(self, status: SystemHealthStatus) -> None:
        """处理不健康状态：通知 + 可选重启。"""
        failed_checks = [c for c in status.checks if not c.passed]
        failed_names = ", ".join(c.name for c in failed_checks)
        detail = "; ".join(c.message for c in failed_checks)

        level = (
            NotificationLevel.CRITICAL
            if status.status == SystemHealthLevel.UNHEALTHY
            else NotificationLevel.WARNING
        )

        logger.warning("健康检查异常: [%s] %s", failed_names, detail)

        if self._notification_hub:
            self._notification_hub.notify(NotificationMessage(
                title=f"健康检查告警: {status.status.value}",
                body=f"失败项: {failed_names}\n详情: {detail}",
                level=level,
                category="health",
            ))

        # 只有线程死亡才触发重启
        if any(c.name == "thread_alive" and not c.passed for c in status.checks):
            self._try_restart()

    def _try_restart(self) -> None:
        """尝试重启目标线程。"""
        if self._restart_callback is None:
            logger.error("目标线程已死亡且未配置重启回调")
            return
        try:
            logger.info("尝试重启目标线程...")
            self._restart_callback()
            logger.info("目标线程重启成功")
        except Exception as e:
            logger.error("目标线程重启失败: %s", e, exc_info=True)
            if self._notification_hub:
                self._notification_hub.notify(NotificationMessage(
                    title="线程重启失败",
                    body=f"重启回调异常: {e}",
                    level=NotificationLevel.CRITICAL,
                    category="health",
                ))

    def _write_heartbeat_file(self) -> None:
        """将当前时间戳写入心跳文件。"""
        try:
            self._heartbeat_file.write_text(
                datetime.now().isoformat(),
                encoding="utf-8",
            )
        except OSError as e:
            logger.debug("心跳文件写入失败: %s", e)
