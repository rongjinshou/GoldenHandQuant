import asyncio
import logging
from collections import defaultdict
from typing import Callable, Awaitable

EventHandler = Callable[[object], Awaitable[None]]


class EventBus:
    """进程内异步事件总线。

    支持 publish/subscribe 模式，handler 为 async callable。
    回测循环逐步迁移为: publish tick → handlers react。
    """

    def __init__(self) -> None:
        self._subscribers: dict[type, list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[object] = asyncio.Queue()

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event: object) -> None:
        await self._queue.put(event)

    async def start(self) -> None:
        """消费事件队列，分发给注册的 handler。"""
        logger = logging.getLogger("event_bus")
        while True:
            event = await self._queue.get()
            for handler in self._subscribers.get(type(event), []):
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(
                        f"Handler %s failed for %s: %s",
                        getattr(handler, "__name__", str(handler)),
                        type(event).__name__,
                        e,
                    )
            self._queue.task_done()
