from datetime import datetime
from unittest.mock import MagicMock

from src.domain.risk.services.risk_event_dispatcher import RiskEventDispatcher
from src.domain.risk.value_objects.risk_event import RiskEvent, RiskEventType, RiskSeverity


def _make_event() -> RiskEvent:
    return RiskEvent(
        event_type=RiskEventType.CIRCUIT_BREAKER_ON,
        severity=RiskSeverity.CRITICAL,
        message="test event",
    )


def test_dispatch_to_single_notifier():
    dispatcher = RiskEventDispatcher()
    notifier = MagicMock()
    dispatcher.add_notifier(notifier)

    event = _make_event()
    dispatcher.dispatch(event)

    notifier.notify.assert_called_once_with(event)


def test_dispatch_to_multiple_notifiers():
    dispatcher = RiskEventDispatcher()
    n1 = MagicMock()
    n2 = MagicMock()
    dispatcher.add_notifier(n1)
    dispatcher.add_notifier(n2)

    event = _make_event()
    dispatcher.dispatch(event)

    n1.notify.assert_called_once_with(event)
    n2.notify.assert_called_once_with(event)


def test_notifier_exception_does_not_affect_others():
    dispatcher = RiskEventDispatcher()
    n1 = MagicMock()
    n1.notify.side_effect = RuntimeError("boom")
    n2 = MagicMock()
    dispatcher.add_notifier(n1)
    dispatcher.add_notifier(n2)

    event = _make_event()
    dispatcher.dispatch(event)  # should not raise

    n2.notify.assert_called_once_with(event)


def test_dispatch_all():
    dispatcher = RiskEventDispatcher()
    notifier = MagicMock()
    dispatcher.add_notifier(notifier)

    events = [_make_event() for _ in range(3)]
    dispatcher.dispatch_all(events)

    assert notifier.notify.call_count == 3
