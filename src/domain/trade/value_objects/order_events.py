"""订单领域事件。

Order 状态变更时自动产出的领域事件，用于审计溯源和事件驱动。
"""

from dataclasses import dataclass

from src.domain.common.domain_event import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderCreatedEvent(DomainEvent):
    """订单创建事件。"""

    event_type: str = "OrderCreated"
    aggregate_type: str = "Order"


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderSubmittedEvent(DomainEvent):
    """订单提交事件。"""

    event_type: str = "OrderSubmitted"
    aggregate_type: str = "Order"


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderFilledEvent(DomainEvent):
    """订单全部成交事件。"""

    event_type: str = "OrderFilled"
    aggregate_type: str = "Order"


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderPartiallyFilledEvent(DomainEvent):
    """订单部分成交事件。"""

    event_type: str = "OrderPartiallyFilled"
    aggregate_type: str = "Order"


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderCanceledEvent(DomainEvent):
    """订单撤单事件。"""

    event_type: str = "OrderCanceled"
    aggregate_type: str = "Order"


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderRejectedEvent(DomainEvent):
    """订单拒单事件。"""

    event_type: str = "OrderRejected"
    aggregate_type: str = "Order"
