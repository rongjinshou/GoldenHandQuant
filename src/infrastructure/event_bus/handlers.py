import logging

from src.application.order_service import OrderService
from src.infrastructure.event_bus.events import (
    MarketTickEvent,
    OrderFilledEvent,
)

logger = logging.getLogger("event_bus.trade")


async def handle_strategy_execution(
    event: MarketTickEvent,
    strategy,
    sizer,
    order_service: OrderService,
) -> None:
    """MarketTick → 策略生成信号 → 下单"""
    from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
    from src.domain.trade.entities.order import Order
    from src.domain.trade.value_objects.order_direction import OrderDirection

    positions = order_service.get_positions()

    if isinstance(strategy, CrossSectionalStrategy):
        # 对 CrossSectionalStrategy 做特殊路由，这里需要 universe 和 current_time
        # EventBus 路径当前可能不提供 universe，这需要通过其他方式获取或跳过
        # 由于回测的 event_bus=True 还没有完全实现所有依赖，这里提供基本路由避免崩溃
        # 实际应使用 runner.evaluate
        return
    else:
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
