from src.application.anomaly_detector import AnomalyDetector
from src.application.auto_pause_manager import AutoPauseManager
from src.domain.risk.services.anomaly_detectors.base import BaseAnomalyDetector
from src.domain.risk.value_objects.anomaly_event import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyType,
    AutoAction,
)


class FakeDetector(BaseAnomalyDetector):
    def __init__(self, events: list[AnomalyEvent] | None = None) -> None:
        self._events = events or []

    def detect(self) -> list[AnomalyEvent]:
        return self._events


class FakeNotificationGateway:
    def __init__(self) -> None:
        self.sent: list = []

    def send(self, message) -> bool:
        self.sent.append(message)
        return True

    def send_batch(self, messages) -> int:
        for m in messages:
            self.send(m)
        return len(messages)


class TestAnomalyDetector:
    def test_no_detectors_returns_empty(self):
        detector = AnomalyDetector()
        events = detector.run_checks()
        assert events == []

    def test_aggregates_all_detectors(self):
        d1 = FakeDetector([AnomalyEvent(
            anomaly_type=AnomalyType.STRATEGY,
            severity=AnomalySeverity.WARNING,
            source="s1", message="m1",
            metric_value=0.3, threshold=0.4,
        )])
        d2 = FakeDetector([AnomalyEvent(
            anomaly_type=AnomalyType.DATA,
            severity=AnomalySeverity.WARNING,
            source="s2", message="m2",
            metric_value=0.5, threshold=0.6,
        )])

        detector = AnomalyDetector(strategy_detectors=[d1], data_detectors=[d2])
        events = detector.run_checks()
        assert len(events) == 2

    def test_pause_strategy_on_critical(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            state_file = str(Path(td) / "state.json")
            pause_mgr = AutoPauseManager(state_file=state_file)

            event = AnomalyEvent(
                anomaly_type=AnomalyType.STRATEGY,
                severity=AnomalySeverity.CRITICAL,
                source="test_strategy", message="胜率下降",
                metric_value=0.3, threshold=0.45,
                auto_action=AutoAction.PAUSE_STRATEGY,
            )
            d = FakeDetector([event])
            detector = AnomalyDetector(
                strategy_detectors=[d],
                pause_manager=pause_mgr,
            )
            detector.run_checks()

            assert pause_mgr.is_strategy_paused("test_strategy")

    def test_pause_all_on_emergency(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            state_file = str(Path(td) / "state.json")
            pause_mgr = AutoPauseManager(state_file=state_file)

            event = AnomalyEvent(
                anomaly_type=AnomalyType.MARKET,
                severity=AnomalySeverity.CRITICAL,
                source="000300.SH", message="指数暴跌",
                metric_value=-0.05, threshold=-0.03,
                auto_action=AutoAction.PAUSE_ALL,
            )
            d = FakeDetector([event])
            detector = AnomalyDetector(
                market_detectors=[d],
                pause_manager=pause_mgr,
            )
            detector.run_checks()

            assert pause_mgr.is_all_paused

    def test_notification_sent(self):
        gw = FakeNotificationGateway()
        event = AnomalyEvent(
            anomaly_type=AnomalyType.DATA,
            severity=AnomalySeverity.WARNING,
            source="600000.SH", message="数据缺失",
            metric_value=0, threshold=3,
            auto_action=AutoAction.NONE,
        )
        d = FakeDetector([event])
        detector = AnomalyDetector(data_detectors=[d], notification_gateway=gw)
        detector.run_checks()

        assert len(gw.sent) == 1
        assert "数据缺失" in gw.sent[0].body
