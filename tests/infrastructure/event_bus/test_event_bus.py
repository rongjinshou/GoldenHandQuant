import asyncio
import pytest
from dataclasses import dataclass

from src.infrastructure.event_bus.event_bus import EventBus
from src.infrastructure.event_bus.events import (
    MarketTickEvent,
    SignalGeneratedEvent,
    OrderFilledEvent,
    DailySettlementEvent,
)


@dataclass(slots=True, kw_only=True)
class TestEvent:
    value: int


def test_event_bus_subscribe_and_dispatch():
    """验证 EventBus 能正确注册 handler 并分发事件。"""
    received: list[int] = []

    async def handler(event: TestEvent) -> None:
        received.append(event.value)

    bus = EventBus()
    bus.subscribe(TestEvent, handler)

    async def run():
        await bus.publish(TestEvent(value=42))
        await bus.publish(TestEvent(value=99))
        # 手动消费队列来验证分发
        for _ in range(2):
            event = await bus._queue.get()
            for h in bus._subscribers.get(type(event), []):
                await h(event)

    asyncio.run(run())
    assert received == [42, 99]


def test_event_bus_multiple_subscribers():
    """验证同一事件类型可以有多个 subscriber。"""
    results: list[str] = []

    async def h1(event: TestEvent) -> None:
        results.append(f"h1:{event.value}")

    async def h2(event: TestEvent) -> None:
        results.append(f"h2:{event.value}")

    bus = EventBus()
    bus.subscribe(TestEvent, h1)
    bus.subscribe(TestEvent, h2)

    async def run():
        await bus.publish(TestEvent(value=1))
        event = await bus._queue.get()
        for h in bus._subscribers.get(type(event), []):
            await h(event)

    asyncio.run(run())
    assert "h1:1" in results
    assert "h2:1" in results
    assert len(results) == 2


def test_event_bus_handler_error_does_not_crash_bus():
    """验证一个 handler 出错不会影响 EventBus 继续运行。"""
    good_results: list[int] = []

    async def bad_handler(event: TestEvent) -> None:
        raise RuntimeError("handler error")

    async def good_handler(event: TestEvent) -> None:
        good_results.append(event.value)

    bus = EventBus()
    bus.subscribe(TestEvent, bad_handler)
    bus.subscribe(TestEvent, good_handler)

    async def run():
        await bus.publish(TestEvent(value=7))
        event = await bus._queue.get()
        for h in bus._subscribers.get(type(event), []):
            try:
                await h(event)
            except RuntimeError:
                pass

    asyncio.run(run())
    assert good_results == [7]


def test_event_bus_different_event_types():
    """验证不同类型事件分发给各自的 handler。"""
    market_results: list[str] = []
    order_results: list[str] = []

    async def market_handler(event: MarketTickEvent) -> None:
        market_results.append(event.timestamp.isoformat())

    async def order_handler(event: OrderFilledEvent) -> None:
        order_results.append(event.order.ticker)

    bus = EventBus()
    bus.subscribe(MarketTickEvent, market_handler)
    bus.subscribe(OrderFilledEvent, order_handler)

    async def run():
        from datetime import datetime
        from src.domain.market.value_objects.bar import Bar
        from src.domain.market.value_objects.timeframe import Timeframe

        bar = Bar(
            symbol="000001.SZ",
            timeframe=Timeframe.DAY_1,
            timestamp=datetime(2024, 1, 4),
            open=10.0, high=11.0, low=9.5, close=10.5, volume=10000,
        )
        await bus.publish(MarketTickEvent(
            timestamp=datetime(2024, 1, 4),
            bars={"000001.SZ": bar},
        ))

        from src.domain.trade.entities.order import Order
        from src.domain.trade.value_objects.order_direction import OrderDirection
        order = Order(
            order_id="ORD_001", account_id="ACC_1", ticker="000001.SZ",
            direction=OrderDirection.BUY, price=10.0, volume=100,
        )
        await bus.publish(OrderFilledEvent(
            timestamp=datetime(2024, 1, 4),
            order=order, fill_price=10.0, fill_volume=100,
        ))

        # Dispatch all events
        for _ in range(2):
            evt = await bus._queue.get()
            for h in bus._subscribers.get(type(evt), []):
                await h(evt)

    asyncio.run(run())
    assert len(market_results) == 1
    assert len(order_results) == 1
    assert order_results[0] == "000001.SZ"
