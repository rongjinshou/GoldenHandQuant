"""RiskEventDispatcher 测试。

2026-07-10 六西格玛体检 D6: 原版用 MagicMock 造 notifier(领域接口), 违反
testing.md「domain 层测试禁 mock, 用手写 Fake」。
"""

from src.domain.risk.services.risk_event_dispatcher import RiskEventDispatcher
from src.domain.risk.value_objects.risk_event import (
    RiskEvent,
    RiskEventType,
    RiskSeverity,
)


class FakeNotifier:
    """记录收到事件的通知替身; attempts 含抛错前的尝试。"""

    def __init__(self, raises: Exception | None = None):
        self.received: list[RiskEvent] = []
        self.attempts = 0
        self._raises = raises

    def notify(self, event: RiskEvent) -> None:
        self.attempts += 1
        if self._raises is not None:
            raise self._raises
        self.received.append(event)


def _make_event() -> RiskEvent:
    return RiskEvent(
        event_type=RiskEventType.CIRCUIT_BREAKER_ON,
        severity=RiskSeverity.CRITICAL,
        message="test event",
    )


def test_dispatch_to_single_notifier():
    dispatcher = RiskEventDispatcher()
    notifier = FakeNotifier()
    dispatcher.add_notifier(notifier)

    event = _make_event()
    dispatcher.dispatch(event)

    assert notifier.received == [event]


def test_dispatch_to_multiple_notifiers():
    dispatcher = RiskEventDispatcher()
    n1, n2 = FakeNotifier(), FakeNotifier()
    dispatcher.add_notifier(n1)
    dispatcher.add_notifier(n2)

    event = _make_event()
    dispatcher.dispatch(event)

    assert n1.received == [event]
    assert n2.received == [event]


def test_notifier_exception_does_not_affect_others():
    dispatcher = RiskEventDispatcher()
    n1 = FakeNotifier(raises=RuntimeError("boom"))
    n2 = FakeNotifier()
    dispatcher.add_notifier(n1)
    dispatcher.add_notifier(n2)

    event = _make_event()
    dispatcher.dispatch(event)  # 不应上抛

    assert n1.attempts == 1
    assert n2.received == [event]


def test_dispatch_all():
    dispatcher = RiskEventDispatcher()
    notifier = FakeNotifier()
    dispatcher.add_notifier(notifier)

    events = [_make_event() for _ in range(3)]
    dispatcher.dispatch_all(events)

    assert len(notifier.received) == 3
