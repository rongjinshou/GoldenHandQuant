from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class BreakerStatus(StrEnum):
    """熔断器状态。"""
    NORMAL = "NORMAL"
    TRIGGERED = "TRIGGERED"
    COOLDOWN = "COOLDOWN"


@dataclass(slots=True, kw_only=True)
class CircuitBreakerState:
    """熔断器状态值对象。

    Attributes:
        status: 当前状态。
        triggered_at: 触发时间。
        trigger_reason: 触发原因。
        daily_loss_rate: 当日亏损率。
    """
    status: BreakerStatus = BreakerStatus.NORMAL
    triggered_at: datetime | None = None
    trigger_reason: str = ""
    daily_loss_rate: float = 0.0

    @property
    def is_normal(self) -> bool:
        return self.status == BreakerStatus.NORMAL

    @property
    def blocks_all_trading(self) -> bool:
        """TRIGGERED 状态禁止所有交易。"""
        return self.status == BreakerStatus.TRIGGERED

    @property
    def allows_sell_only(self) -> bool:
        """COOLDOWN 状态仅允许卖出。"""
        return self.status == BreakerStatus.COOLDOWN
