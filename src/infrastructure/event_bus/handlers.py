import logging

from src.infrastructure.event_bus.events import OrderFilledEvent

logger = logging.getLogger("event_bus.trade")


async def handle_order_logging(event: OrderFilledEvent) -> None:
    """记录每笔成交到日志。"""
    logger.info(
        f"FILLED | {event.timestamp} | {event.order.ticker} | "
        f"{event.order.direction.name} | qty={event.fill_volume} | "
        f"price={event.fill_price:.2f}"
    )
