import threading
import time as time_mod
from datetime import datetime
from unittest.mock import MagicMock

from src.application.health_service import HealthService
from src.domain.trade.value_objects.health_status import (
    CheckResult,
    SystemHealthLevel,
    SystemHealthStatus,
)


class TestCheckResult:
    def test_check_result_should_store_fields(self):
        now = datetime.now()
        result = CheckResult(name="test_check", passed=True, message="ok", checked_at=now)
        assert result.name == "test_check"
        assert result.passed is True
        assert result.message == "ok"
        assert result.checked_at == now

    def test_check_result_should_default_message_to_empty(self):
        result = CheckResult(name="test", passed=False)
        assert result.message == ""

    def test_check_result_should_default_checked_at(self):
        before = datetime.now()
        result = CheckResult(name="test", passed=True)
        after = datetime.now()
        assert before <= result.checked_at <= after


class TestSystemHealthStatus:
    def test_from_checks_all_passed_should_be_healthy(self):
        checks = [
            CheckResult(name="a", passed=True),
            CheckResult(name="b", passed=True),
        ]
        now = datetime.now()
        status = SystemHealthStatus.from_checks(checks, now, 100.0)
        assert status.status == SystemHealthLevel.HEALTHY
        assert status.is_healthy
        assert status.heartbeat_time == now
        assert status.uptime_seconds == 100.0

    def test_from_checks_minority_failed_should_be_degraded(self):
        checks = [
            CheckResult(name="a", passed=True),
            CheckResult(name="b", passed=True),
            CheckResult(name="c", passed=False),
        ]
        status = SystemHealthStatus.from_checks(checks, datetime.now(), 50.0)
        assert status.status == SystemHealthLevel.DEGRADED
        assert not status.is_healthy

    def test_from_checks_half_or_more_failed_should_be_unhealthy(self):
        checks = [
            CheckResult(name="a", passed=False),
            CheckResult(name="b", passed=False),
            CheckResult(name="c", passed=True),
        ]
        status = SystemHealthStatus.from_checks(checks, datetime.now(), 10.0)
        assert status.status == SystemHealthLevel.UNHEALTHY

    def test_from_checks_empty_list_should_be_healthy(self):
        status = SystemHealthStatus.from_checks([], datetime.now(), 0.0)
        assert status.status == SystemHealthLevel.HEALTHY

    def test_from_checks_single_failed_should_be_unhealthy(self):
        checks = [CheckResult(name="only", passed=False)]
        status = SystemHealthStatus.from_checks(checks, datetime.now(), 5.0)
        assert status.status == SystemHealthLevel.UNHEALTHY


class TestHealthService:
    """HealthService 测试。"""

    def _make_alive_thread(self) -> threading.Thread:
        """创建一个会存活一段时间的线程。"""
        event = threading.Event()

        def _run():
            event.wait(timeout=30)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        # 用 event 让外部可以停止它
        t._stop_event = event  # type: ignore[attr-defined]
        return t

    def _stop_thread(self, t: threading.Thread) -> None:
        if hasattr(t, "_stop_event"):
            t._stop_event.set()  # type: ignore[attr-defined]

    def test_get_health_status_all_healthy(self, tmp_path):
        # Arrange
        thread = self._make_alive_thread()
        hb_file = tmp_path / "heartbeat"
        service = HealthService(
            target_thread=thread,
            heartbeat_file=hb_file,
            heartbeat_timeout_seconds=60.0,
        )
        service.beat()

        # Act
        status = service.get_health_status()

        # Assert
        assert status.is_healthy
        assert len(status.checks) == 3
        assert all(c.passed for c in status.checks)
        assert status.uptime_seconds >= 0

        # Cleanup
        service.stop()
        self._stop_thread(thread)

    def test_get_health_status_thread_dead_should_be_unhealthy(self, tmp_path):
        # Arrange: 创建一个已结束的线程
        thread = threading.Thread(target=lambda: None)
        thread.start()
        thread.join()  # 线程立即结束
        hb_file = tmp_path / "heartbeat"
        service = HealthService(
            target_thread=thread,
            heartbeat_file=hb_file,
            heartbeat_timeout_seconds=60.0,
        )
        service.beat()

        # Act
        status = service.get_health_status()

        # Assert
        thread_check = next(c for c in status.checks if c.name == "thread_alive")
        assert not thread_check.passed

    def test_get_health_status_heartbeat_timeout_should_fail(self, tmp_path):
        # Arrange
        thread = self._make_alive_thread()
        hb_file = tmp_path / "heartbeat"
        service = HealthService(
            target_thread=thread,
            heartbeat_file=hb_file,
            heartbeat_timeout_seconds=0.01,  # 极短超时
        )
        service.beat()
        time_mod.sleep(0.05)  # 等待超过超时

        # Act
        status = service.get_health_status()

        # Assert
        hb_check = next(c for c in status.checks if c.name == "heartbeat")
        assert not hb_check.passed

        # Cleanup
        service.stop()
        self._stop_thread(thread)

    def test_beat_should_write_heartbeat_file(self, tmp_path):
        # Arrange
        thread = self._make_alive_thread()
        hb_file = tmp_path / "heartbeat"
        service = HealthService(
            target_thread=thread,
            heartbeat_file=hb_file,
            heartbeat_timeout_seconds=60.0,
        )

        # Act
        service.beat()

        # Assert
        assert hb_file.exists()
        content = hb_file.read_text(encoding="utf-8")
        # 验证写入的是 ISO 格式时间
        datetime.fromisoformat(content)

        # Cleanup
        service.stop()
        self._stop_thread(thread)

    def test_start_stop_should_manage_watchdog_thread(self, tmp_path):
        # Arrange
        thread = self._make_alive_thread()
        hb_file = tmp_path / "heartbeat"
        service = HealthService(
            target_thread=thread,
            heartbeat_file=hb_file,
        )

        # Act & Assert
        assert not service.is_running
        service.start()
        assert service.is_running
        service.stop()
        assert not service.is_running

        # Cleanup
        self._stop_thread(thread)

    def test_start_twice_should_not_create_duplicate(self, tmp_path):
        # Arrange
        thread = self._make_alive_thread()
        hb_file = tmp_path / "heartbeat"
        service = HealthService(
            target_thread=thread,
            heartbeat_file=hb_file,
        )

        # Act
        service.start()
        service.start()  # 第二次不应报错

        # Assert
        assert service.is_running

        # Cleanup
        service.stop()
        self._stop_thread(thread)

    def test_watchdog_should_call_restart_on_thread_death(self, tmp_path):
        # Arrange
        dead_thread = threading.Thread(target=lambda: None)
        dead_thread.start()
        dead_thread.join()

        restart_called = threading.Event()
        hb_file = tmp_path / "heartbeat"
        service = HealthService(
            target_thread=dead_thread,
            restart_callback=restart_called.set,
            heartbeat_file=hb_file,
            check_interval_seconds=0.1,
        )

        # Act
        service.start()
        restart_called.wait(timeout=2.0)

        # Assert
        assert restart_called.is_set()

        # Cleanup
        service.stop()

    def test_watchdog_should_notify_on_unhealthy(self, tmp_path):
        # Arrange
        dead_thread = threading.Thread(target=lambda: None)
        dead_thread.start()
        dead_thread.join()

        mock_hub = MagicMock()
        hb_file = tmp_path / "heartbeat"
        service = HealthService(
            target_thread=dead_thread,
            notification_hub=mock_hub,
            heartbeat_file=hb_file,
            check_interval_seconds=0.1,
        )

        # Act
        service.start()
        time_mod.sleep(0.5)

        # Assert
        assert mock_hub.notify.call_count >= 1
        call_args = mock_hub.notify.call_args_list[0][0][0]
        assert "健康检查告警" in call_args.title

        # Cleanup
        service.stop()

    def test_watchdog_should_notify_restart_failure(self, tmp_path):
        # Arrange
        dead_thread = threading.Thread(target=lambda: None)
        dead_thread.start()
        dead_thread.join()

        def _bad_restart():
            raise RuntimeError("重启失败")

        mock_hub = MagicMock()
        hb_file = tmp_path / "heartbeat"
        service = HealthService(
            target_thread=dead_thread,
            restart_callback=_bad_restart,
            notification_hub=mock_hub,
            heartbeat_file=hb_file,
            check_interval_seconds=0.1,
        )

        # Act
        service.start()
        time_mod.sleep(0.5)

        # Assert: 应该至少收到 2 条通知（健康告警 + 重启失败）
        assert mock_hub.notify.call_count >= 2
        titles = [call[0][0].title for call in mock_hub.notify.call_args_list]
        assert any("重启失败" in t for t in titles)

        # Cleanup
        service.stop()

    def test_get_health_status_should_include_uptime(self, tmp_path):
        # Arrange
        thread = self._make_alive_thread()
        hb_file = tmp_path / "heartbeat"
        service = HealthService(
            target_thread=thread,
            heartbeat_file=hb_file,
        )

        # Act
        time_mod.sleep(0.05)
        status = service.get_health_status()

        # Assert
        assert status.uptime_seconds >= 0.05

        # Cleanup
        service.stop()
        self._stop_thread(thread)
