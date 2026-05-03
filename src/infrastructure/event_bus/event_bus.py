import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable

EventHandler = Callable[[object], Awaitable[None]]


class EventBus:
    """进程内异步事件总线。

    支持 publish/subscribe 模式，handler 为 async callable。
    回测循环逐步迁移为: publish tick → handlers react。
    """

    def __init__(self, max_queue_size: int = 10000) -> None:
        self._subscribers: dict[type, list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[object] = asyncio.Queue(maxsize=max_queue_size)
        self._running = False

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event: object) -> None:
        if not self._subscribers:
            return  # 无订阅者时静默丢弃，防止内存泄漏
        await self._queue.put(event)

    async def start(self) -> None:
        """消费事件队列，分发给注册的 handler。"""
        logger = logging.getLogger("event_bus")
        self._running = True
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            for handler in self._subscribers.get(type(event), []):
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(
                        "Handler %s failed for %s: %s",
                        getattr(handler, "__name__", str(handler)),
                        type(event).__name__,
                        e,
                    )
            self._queue.task_done()

    def stop(self) -> None:
        """停止事件总线消费循环。"""
        self._running = False
