"""Order 实体领域事件测试。"""

from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection


class TestOrderDomainEvents:
    def _make_order(self) -> Order:
        return Order(
            order_id="order-1",
            account_id="acc-1",
            ticker="600000.SH",
            direction=OrderDirection.BUY,
            price=10.0,
            volume=100,
        )

    def test_new_order_has_no_pending_events(self):
        order = self._make_order()
        events = order.collect_pending_events()
        assert events == []

    def test_submit_emits_order_submitted_event(self):
        # Arrange
        order = self._make_order()

        # Act
        order.submit()
        events = order.collect_pending_events()

        # Assert
        assert len(events) == 1
        assert events[0].event_type == "OrderSubmitted"
        assert events[0].aggregate_id == "order-1"
        assert events[0].aggregate_type == "Order"
        assert events[0].payload["ticker"] == "600000.SH"
        assert events[0].payload["direction"] == "BUY"

    def test_on_fill_emits_order_filled_event(self):
        # Arrange
        order = self._make_order()
        order.submit()
        order.collect_pending_events()  # clear submit event

        # Act
        order.on_fill(100, 10.5)
        events = order.collect_pending_events()

        # Assert
        assert len(events) == 1
        assert events[0].event_type == "OrderFilled"
        assert events[0].payload["fill_volume"] == 100
        assert events[0].payload["fill_price"] == 10.5
        assert events[0].payload["new_status"] == "FILLED"

    def test_cancel_emits_order_canceled_event(self):
        # Arrange
        order = self._make_order()
        order.submit()
        order.collect_pending_events()

        # Act
        order.cancel()
        events = order.collect_pending_events()

        # Assert
        assert len(events) == 1
        assert events[0].event_type == "OrderCanceled"
        assert events[0].payload["final_status"] == "CANCELED"

    def test_reject_emits_order_rejected_event(self):
        # Arrange
        order = self._make_order()
        order.submit()
        order.collect_pending_events()

        # Act
        order.reject("风控拦截")
        events = order.collect_pending_events()

        # Assert
        assert len(events) == 1
        assert events[0].event_type == "OrderRejected"
        assert events[0].payload["reason"] == "风控拦截"

    def test_collect_pending_events_clears_buffer(self):
        # Arrange
        order = self._make_order()
        order.submit()

        # Act
        first_collect = order.collect_pending_events()
        second_collect = order.collect_pending_events()

        # Assert
        assert len(first_collect) == 1
        assert len(second_collect) == 0

    def test_full_lifecycle_emits_all_events(self):
        # Arrange
        order = self._make_order()

        # Act
        order.submit()
        order.on_fill(50, 10.5)  # partial fill
        order.on_fill(50, 10.6)  # full fill
        events = order.collect_pending_events()

        # Assert
        assert len(events) == 3
        event_types = [e.event_type for e in events]
        assert event_types == ["OrderSubmitted", "OrderFilled", "OrderFilled"]
