"""持仓差异值对象。"""

from dataclasses import dataclass
from enum import StrEnum


class DifferenceType(StrEnum):
    """差异类型。"""
    MISSING_IN_BROKER = "missing_in_broker"    # 系统有、券商无
    MISSING_IN_SYSTEM = "missing_in_system"    # 券商有、系统无
    VOLUME_MISMATCH = "volume_mismatch"        # 数量不一致
    COST_MISMATCH = "cost_mismatch"            # 成本不一致（容忍精度）


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionDifference:
    """持仓差异 — 记录系统持仓与券商持仓之间的单条差异。

    Attributes:
        ticker: 证券代码。
        diff_type: 差异类型。
        system_volume: 系统记录的总持仓数量。
        broker_volume: 券商返回的总持仓数量。
        system_cost: 系统记录的持仓均价。
        broker_cost: 券商返回的持仓均价。
        detail: 人类可读的差异描述。
    """

    ticker: str
    diff_type: DifferenceType
    system_volume: int = 0
    broker_volume: int = 0
    system_cost: float = 0.0
    broker_cost: float = 0.0
    detail: str = ""
