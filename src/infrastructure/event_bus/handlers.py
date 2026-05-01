import logging

from src.infrastructure.event_bus.events import (
    MarketTickEvent,
    SignalGeneratedEvent,
    OrderFilledEvent,
    DailySettlementEvent,
)
from src.application.order_service import OrderService

logger = logging.getLogger("event_bus.trade")


async def handle_strategy_execution(
    event: MarketTickEvent,
    strategy,
    sizer,
    order_service: OrderService,
) -> None:
    """MarketTick → 策略生成信号 → 下单"""
    from src.domain.trade.entities.order import Order
    from src.domain.trade.value_objects.order_direction import OrderDirection

    positions = order_service.get_positions()
    signals = strategy.generate_signals(event.bars, positions)
    for signal in signals:
        asset = order_service.get_asset()
        position = next((p for p in positions if p.ticker == signal.symbol), None)
        price = event.bars[signal.symbol].open if signal.symbol in event.bars else 0.0
        volume = sizer.calculate_target(signal, price, asset, position)
        if volume > 0:
            order = Order(
                order_id=f"ORD_{event.timestamp.strftime('%Y%m%d%H%M%S')}_{signal.symbol}",
                account_id=asset.account_id,
                ticker=signal.symbol,
                direction=OrderDirection(signal.direction.value),
                price=price,
                volume=volume,
            )
            order_service.place_order(order)


async def handle_order_logging(event: OrderFilledEvent) -> None:
    """记录每笔成交到日志。"""
    logger.info(
        f"FILLED | {event.timestamp} | {event.order.ticker} | "
        f"{event.order.direction.name} | qty={event.fill_volume} | "
        f"price={event.fill_price:.2f}"
    )
