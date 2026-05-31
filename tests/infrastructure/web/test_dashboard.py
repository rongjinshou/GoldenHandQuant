import tempfile
from pathlib import Path

from src.application.auto_pause_manager import AutoPauseManager
from src.domain.trade.services.execution_monitor import ExecutionMonitor
from src.domain.trade.value_objects.execution_record import ExecutionRecord
from src.domain.trade.value_objects.execution_status import ExecutionStatus
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.infrastructure.web.auth import TokenAuth
from src.infrastructure.web.dashboard import WebDashboard


def _make_monitor_with_data() -> ExecutionMonitor:
    monitor = ExecutionMonitor()
    monitor.record(ExecutionRecord(
        order_id="1",
        symbol="600000.SH",
        direction=OrderDirection.BUY,
        target_price=10.0,
        target_volume=100,
        status=ExecutionStatus.FILLED,
    ))
    return monitor


class TestTokenAuth:
    def test_verify_valid_token(self):
        auth = TokenAuth("secret-token")
        assert auth.verify("secret-token") is True

    def test_verify_invalid_token(self):
        auth = TokenAuth("secret-token")
        assert auth.verify("wrong-token") is False

    def test_verify_empty_token_config(self):
        auth = TokenAuth("")
        assert auth.verify("any-token") is False

    def test_mask_sensitive(self):
        masked = TokenAuth.mask_sensitive("account12345678")
        assert "****" in masked


class TestWebDashboard:
    def test_get_status_stopped(self):
        dashboard = WebDashboard()
        status = dashboard.get_status()
        assert status["status"] == "stopped"

    def test_get_stats(self):
        monitor = _make_monitor_with_data()
        dashboard = WebDashboard(execution_monitor=monitor)
        stats = dashboard.get_stats()
        assert stats["total_orders"] == 1

    def test_get_health(self):
        monitor = _make_monitor_with_data()
        dashboard = WebDashboard(execution_monitor=monitor)
        health = dashboard.get_health()
        assert health["health"] in ("healthy", "warning", "critical")

    def test_pause_and_resume(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = str(Path(td) / "state.json")
            pause_mgr = AutoPauseManager(state_file=state_file)
            auth = TokenAuth("test-token")
            dashboard = WebDashboard(pause_manager=pause_mgr, auth=auth)

            result = dashboard.pause("test-token")
            assert result["status"] == "paused"
            assert pause_mgr.is_all_paused

            result = dashboard.resume("test-token")
            assert result["status"] == "resumed"
            assert not pause_mgr.is_all_paused

    def test_pause_unauthorized(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = str(Path(td) / "state.json")
            pause_mgr = AutoPauseManager(state_file=state_file)
            auth = TokenAuth("test-token")
            dashboard = WebDashboard(pause_manager=pause_mgr, auth=auth)

            result = dashboard.pause("wrong-token")
            assert "error" in result

    def test_event_queue(self):
        dashboard = WebDashboard()
        q = dashboard.add_event_queue()
        dashboard._push_event("test", {"key": "value"})
        event = q.get(timeout=1)
        assert event["type"] == "test"
        dashboard.remove_event_queue(q)
