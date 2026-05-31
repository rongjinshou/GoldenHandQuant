from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyAllocation:
    """单个策略的资金分配结果。

    Attributes:
        strategy_name: 策略名称。
        allocated_capital: 分配的资金总额。
        weight: 权重 (0.0 - 1.0)。
        allocated_at: 分配时间。
        reason: 分配原因说明。
    """

    strategy_name: str
    allocated_capital: float
    weight: float
    allocated_at: datetime
    reason: str = ""

    def __post_init__(self) -> None:
        if self.allocated_capital < 0:
            raise ValueError(f"allocated_capital must be >= 0, got {self.allocated_capital}")
        if not (0.0 <= self.weight <= 1.0):
            raise ValueError(f"weight must be in [0.0, 1.0], got {self.weight}")


@dataclass(frozen=True, slots=True, kw_only=True)
class AllocationResult:
    """一次完整的资金分配结果。

    Attributes:
        total_capital: 可分配总资金。
        allocations: 各策略的分配结果列表。
        algorithm: 使用的分配算法名称。
        created_at: 分配创建时间。
    """

    total_capital: float
    allocations: list[StrategyAllocation]
    algorithm: str
    created_at: datetime

    @property
    def weight_sum(self) -> float:
        return sum(a.weight for a in self.allocations)
