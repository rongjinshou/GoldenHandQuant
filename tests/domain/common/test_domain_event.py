"""DomainEvent 基类测试（纯标准库，零第三方依赖）。"""

from datetime import datetime

from src.domain.common.domain_event import DomainEvent


class TestDomainEvent:
    def test_create_with_required_fields_should_generate_event_id(self):
        # Arrange & Act
        event = DomainEvent(
            event_type="OrderSubmitted",
            aggregate_id="order-1",
            aggregate_type="Order",
        )

        # Assert
        assert event.event_type == "OrderSubmitted"
        assert event.aggregate_id == "order-1"
        assert event.aggregate_type == "Order"
        assert isinstance(event.event_id, str) and len(event.event_id) > 0
        assert isinstance(event.timestamp, datetime)
        assert event.payload == {}

    def test_create_with_payload_should_store_data(self):
        # Arrange & Act
        event = DomainEvent(
            event_type="OrderFilled",
            aggregate_id="order-2",
            aggregate_type="Order",
            payload={"fill_volume": 100, "fill_price": 10.5},
        )

        # Assert
        assert event.payload["fill_volume"] == 100
        assert event.payload["fill_price"] == 10.5

    def test_domain_event_should_be_frozen(self):
        # Arrange
        event = DomainEvent(
            event_type="TestEvent",
            aggregate_id="agg-1",
            aggregate_type="Test",
        )

        # Act & Assert
        try:
            event.event_type = "Changed"
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass

    def test_with_aggregate_should_create_new_event_bound_to_aggregate(self):
        # Arrange
        event = DomainEvent(
            event_type="OrderSubmitted",
            aggregate_id="",
            aggregate_type="",
            payload={"ticker": "600000.SH"},
        )

        # Act
        bound_event = event.with_aggregate("order-123", "Order")

        # Assert
        assert bound_event.aggregate_id == "order-123"
        assert bound_event.aggregate_type == "Order"
        assert bound_event.event_id == event.event_id  # same ID preserved
        assert bound_event.payload == {"ticker": "600000.SH"}
