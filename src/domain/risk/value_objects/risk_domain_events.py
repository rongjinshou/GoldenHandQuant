"""风控领域事件。

CircuitBreaker 状态变更时自动产出的领域事件。
"""

from dataclasses import dataclass

from src.domain.common.domain_event import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class CircuitBreakerTriggeredEvent(DomainEvent):
    """熔断器触发事件。"""

    event_type: str = "CircuitBreakerTriggered"
    aggregate_type: str = "CircuitBreaker"


@dataclass(frozen=True, slots=True, kw_only=True)
class CircuitBreakerCooldownEvent(DomainEvent):
    """熔断器进入冷却期事件。"""

    event_type: str = "CircuitBreakerCooldown"
    aggregate_type: str = "CircuitBreaker"


@dataclass(frozen=True, slots=True, kw_only=True)
class CircuitBreakerRecoveredEvent(DomainEvent):
    """熔断器恢复事件。"""

    event_type: str = "CircuitBreakerRecovered"
    aggregate_type: str = "CircuitBreaker"
