from dataclasses import dataclass
from datetime import datetime

from src.domain.market.value_objects.bar import Bar
from src.domain.trade.entities.order import Order
from src.domain.strategy.value_objects.signal import Signal


@dataclass(slots=True, kw_only=True)
class MarketTickEvent:
    timestamp: datetime
    bars: dict[str, Bar]


@dataclass(slots=True, kw_only=True)
class SignalGeneratedEvent:
    timestamp: datetime
    signals: list[Signal]


@dataclass(slots=True, kw_only=True)
class OrderFilledEvent:
    timestamp: datetime
    order: Order
    fill_price: float
    fill_volume: int


@dataclass(slots=True, kw_only=True)
class DailySettlementEvent:
    timestamp: datetime
    date: datetime
