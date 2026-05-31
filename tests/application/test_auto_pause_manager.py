import json
import tempfile
from pathlib import Path

from src.application.auto_pause_manager import AutoPauseManager
from src.domain.risk.value_objects.anomaly_event import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyType,
    AutoAction,
)


def _make_event(
    message: str = "test anomaly",
    severity: AnomalySeverity = AnomalySeverity.CRITICAL,
) -> AnomalyEvent:
    return AnomalyEvent(
        anomaly_type=AnomalyType.STRATEGY,
        severity=severity,
        source="test_strategy",
        message=message,
        metric_value=0.3,
        threshold=0.45,
        auto_action=AutoAction.PAUSE_STRATEGY,
    )


class TestAutoPauseManager:
    def test_pause_and_resume_strategy(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = str(Path(td) / "state.json")
            mgr = AutoPauseManager(state_file=state_file)

            event = _make_event()
            mgr.pause_strategy("test_strategy", event)

            assert mgr.is_strategy_paused("test_strategy")
            assert not mgr.is_strategy_paused("other_strategy")

            mgr.resume("test_strategy", operator="test")
            assert not mgr.is_strategy_paused("test_strategy")

    def test_pause_all(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = str(Path(td) / "state.json")
            mgr = AutoPauseManager(state_file=state_file)

            event = _make_event(message="市场暴跌")
            mgr.pause_all(event)

            assert mgr.is_all_paused
            assert mgr.is_strategy_paused("any_strategy")

            mgr.resume_all(operator="test")
            assert not mgr.is_all_paused
            assert not mgr.is_strategy_paused("any_strategy")

    def test_state_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = str(Path(td) / "state.json")
            mgr = AutoPauseManager(state_file=state_file)

            event = _make_event()
            mgr.pause_strategy("test_strategy", event)

            # Reload from file
            mgr2 = AutoPauseManager(state_file=state_file)
            assert mgr2.is_strategy_paused("test_strategy")

    def test_get_status(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = str(Path(td) / "state.json")
            mgr = AutoPauseManager(state_file=state_file)

            event = _make_event()
            mgr.pause_strategy("strategy_a", event)

            status = mgr.get_status()
            assert len(status) == 1
            assert status[0].strategy_name == "strategy_a"
            assert status[0].is_paused

    def test_resume_nonexistent_strategy(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = str(Path(td) / "state.json")
            mgr = AutoPauseManager(state_file=state_file)
            mgr.resume("nonexistent")  # Should not raise

    def test_double_pause_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = str(Path(td) / "state.json")
            mgr = AutoPauseManager(state_file=state_file)

            event = _make_event()
            mgr.pause_strategy("test_strategy", event)
            mgr.pause_strategy("test_strategy", event)  # Second pause

            status = mgr.get_status()
            assert len(status) == 1
