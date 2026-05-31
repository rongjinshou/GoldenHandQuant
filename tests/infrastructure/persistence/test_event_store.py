"""SQLiteEventStore 测试。"""

from datetime import datetime, timezone

from src.domain.common.domain_event import DomainEvent
from src.infrastructure.persistence.database import Database
from src.infrastructure.persistence.event_store import SQLiteEventStore


def _make_event(
    event_type: str = "OrderSubmitted",
    aggregate_id: str = "order-1",
    aggregate_type: str = "Order",
    payload: dict | None = None,
) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        payload=payload or {},
    )


class TestSQLiteEventStore:
    def _create_store(self, tmp_path=None):
        db = Database(":memory:")
        return SQLiteEventStore(db)

    def test_append_single_event(self):
        store = self._create_store()
        event = _make_event(payload={"ticker": "600000.SH"})

        store.append(event)

        events = store.get_events_by_aggregate("order-1")
        assert len(events) == 1
        assert events[0].event_type == "OrderSubmitted"
        assert events[0].payload["ticker"] == "600000.SH"

    def test_append_batch(self):
        store = self._create_store()
        events = [
            _make_event(event_type="OrderSubmitted", aggregate_id="order-1"),
            _make_event(event_type="OrderFilled", aggregate_id="order-1"),
            _make_event(event_type="OrderSubmitted", aggregate_id="order-2"),
        ]

        store.append_batch(events)

        order1_events = store.get_events_by_aggregate("order-1")
        assert len(order1_events) == 2

        order2_events = store.get_events_by_aggregate("order-2")
        assert len(order2_events) == 1

    def test_append_batch_empty_list(self):
        store = self._create_store()
        store.append_batch([])
        assert store.get_events(limit=10) == []

    def test_get_events_filter_by_event_type(self):
        store = self._create_store()
        store.append_batch([
            _make_event(event_type="OrderSubmitted", aggregate_id="order-1"),
            _make_event(event_type="OrderFilled", aggregate_id="order-1"),
            _make_event(event_type="OrderSubmitted", aggregate_id="order-2"),
        ])

        submitted = store.get_events(event_type="OrderSubmitted")
        assert len(submitted) == 2

        filled = store.get_events(event_type="OrderFilled")
        assert len(filled) == 1

    def test_get_events_filter_by_aggregate_id(self):
        store = self._create_store()
        store.append_batch([
            _make_event(aggregate_id="order-1"),
            _make_event(aggregate_id="order-2"),
            _make_event(aggregate_id="order-1"),
        ])

        events = store.get_events(aggregate_id="order-1")
        assert len(events) == 2

    def test_get_events_filter_by_time_range(self):
        store = self._create_store()

        t1 = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc)

        store.append(DomainEvent(
            event_type="E1", aggregate_id="a", aggregate_type="T", timestamp=t1,
        ))
        store.append(DomainEvent(
            event_type="E2", aggregate_id="a", aggregate_type="T", timestamp=t2,
        ))
        store.append(DomainEvent(
            event_type="E3", aggregate_id="a", aggregate_type="T", timestamp=t3,
        ))

        events = store.get_events(start_time=t1, end_time=t2)
        assert len(events) == 2
        assert events[0].event_type == "E1"
        assert events[1].event_type == "E2"

    def test_get_events_limit(self):
        store = self._create_store()
        for i in range(10):
            store.append(_make_event(aggregate_id=f"order-{i}"))

        events = store.get_events(limit=5)
        assert len(events) == 5

    def test_events_ordered_by_timestamp(self):
        store = self._create_store()
        store.append(DomainEvent(
            event_type="E1", aggregate_id="a", aggregate_type="T",
            timestamp=datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
        ))
        store.append(DomainEvent(
            event_type="E2", aggregate_id="a", aggregate_type="T",
            timestamp=datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
        ))

        events = store.get_events_by_aggregate("a")
        assert events[0].event_type == "E2"  # earlier timestamp first
        assert events[1].event_type == "E1"
