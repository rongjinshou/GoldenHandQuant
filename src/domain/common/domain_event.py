"""领域事件基类（纯标准库，零第三方依赖）。

所有领域事件继承自 DomainEvent，不可变值对象，使用 frozen=True 保证事件不被篡改。
事件通过 aggregate_id 关联到聚合根（如 Order、CircuitBreaker）。
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Self
from uuid import uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    """领域事件基类。

    Attributes:
        event_id: 全局唯一事件 ID (UUID)。
        event_type: 事件类型标识（如 "OrderSubmitted"、"CircuitBreakerTriggered"）。
        aggregate_id: 聚合根 ID（如 order_id）。
        aggregate_type: 聚合根类型（如 "Order"、"CircuitBreaker"）。
        timestamp: 事件发生时间（UTC）。
        payload: 事件附加数据（不可变字典）。
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: str
    aggregate_id: str
    aggregate_type: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, object] = field(default_factory=dict)

    def with_aggregate(self, aggregate_id: str, aggregate_type: str) -> Self:
        """基于当前事件创建新事件并绑定聚合根。

        Args:
            aggregate_id: 聚合根 ID。
            aggregate_type: 聚合根类型。

        Returns:
            绑定了聚合根的新事件实例。
        """
        return type(self)(
            event_id=self.event_id,
            event_type=self.event_type,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            timestamp=self.timestamp,
            payload=self.payload,
        )
