"""Order 实体领域事件测试。

验证 Order 状态变更时正确产出领域事件。
"""

from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_status import OrderStatus


def _make_buy_order(order_id: str = "order-001") -> Order:
    """创建测试用买入订单。"""
    return Order(
        order_id=order_id,
        account_id="acc-001",
        ticker="000001.SZ",
        direction=OrderDirection.BUY,
        price=10.0,
        volume=100,
    )


class TestOrderEventEmission:
    """Order 状态变更事件产出测试。"""

    def test_submit_emits_order_submitted_event(self) -> None:
        """提交订单应产出 OrderSubmitted 事件。"""
        order = _make_buy_order()
        events = order.collect_pending_events()
        assert len(events) == 0  # 创建时不产事件

        order.submit()
        events = order.collect_pending_events()

        assert len(events) == 1
        event = events[0]
        assert event.event_type == "OrderSubmitted"
        assert event.aggregate_id == "order-001"
        assert event.aggregate_type == "Order"
        assert event.payload["ticker"] == "000001.SZ"
        assert event.payload["direction"] == "BUY"
        assert event.payload["price"] == 10.0
        assert event.payload["volume"] == 100

    def test_fill_emits_order_filled_event(self) -> None:
        """全部成交应产出 OrderFilled 事件。"""
        order = _make_buy_order()
        order.submit()
        order.collect_pending_events()  # 清除 submit 事件

        order.on_fill(fill_volume=100, fill_price=10.05)
        events = order.collect_pending_events()

        assert len(events) == 1
        event = events[0]
        assert event.event_type == "OrderFilled"
        assert event.payload["fill_volume"] == 100
        assert event.payload["fill_price"] == 10.05
        assert event.payload["new_status"] == "FILLED"

    def test_partial_fill_emits_order_filled_event(self) -> None:
        """部分成交也产出 OrderFilled 事件（event_type 为 OrderFilled）。"""
        order = _make_buy_order()
        order.submit()
        order.collect_pending_events()

        order.on_fill(fill_volume=50, fill_price=10.0)
        events = order.collect_pending_events()

        assert len(events) == 1
        assert events[0].event_type == "OrderFilled"
        assert events[0].payload["new_status"] == "PARTIAL_FILLED"

    def test_cancel_emits_order_canceled_event(self) -> None:
        """撤单应产出 OrderCanceled 事件。"""
        order = _make_buy_order()
        order.submit()
        order.collect_pending_events()

        order.cancel()
        events = order.collect_pending_events()

        assert len(events) == 1
        assert events[0].event_type == "OrderCanceled"
        assert events[0].payload["final_status"] == "CANCELED"

    def test_reject_emits_order_rejected_event(self) -> None:
        """拒单应产出 OrderRejected 事件。"""
        order = _make_buy_order()
        order.submit()
        order.collect_pending_events()

        order.reject(reason="涨跌停限制")
        events = order.collect_pending_events()

        assert len(events) == 1
        assert events[0].event_type == "OrderRejected"
        assert events[0].payload["reason"] == "涨跌停限制"

    def test_collect_pending_events_clears_buffer(self) -> None:
        """collect_pending_events 应清空内部缓冲区。"""
        order = _make_buy_order()
        order.submit()

        events1 = order.collect_pending_events()
        events2 = order.collect_pending_events()

        assert len(events1) == 1
        assert len(events2) == 0

    def test_full_lifecycle_produces_all_events(self) -> None:
        """完整订单生命周期应产出正确的事件序列。"""
        order = _make_buy_order()

        # 提交
        order.submit()
        # 部分成交
        order.on_fill(fill_volume=50, fill_price=10.0)
        # 撤单（部分成交后撤单 -> PARTIAL_CANCELED）
        order.cancel()

        events = order.collect_pending_events()

        assert len(events) == 3
        assert events[0].event_type == "OrderSubmitted"
        assert events[1].event_type == "OrderFilled"
        assert events[2].event_type == "OrderCanceled"
        assert events[2].payload["final_status"] == "PARTIAL_CANCELED"

    def test_sell_order_events_contain_correct_direction(self) -> None:
        """卖出订单的事件应包含 SELL 方向。"""
        order = Order(
            order_id="order-sell-001",
            account_id="acc-001",
            ticker="000001.SZ",
            direction=OrderDirection.SELL,
            price=10.5,
            volume=200,
        )

        order.submit()
        events = order.collect_pending_events()

        assert events[0].payload["direction"] == "SELL"
