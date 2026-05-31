from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionSnapshot:
    """Dashboard 持仓快照。"""

    ticker: str
    total_volume: int
    available_volume: int
    average_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    pnl_ratio: float


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskStatus:
    """Dashboard 风控状态。"""

    total_position_ratio: float
    max_concentration: float
    position_count: int
    today_drawdown: float = 0.0
    alert_count: int = 0
    is_circuit_breaker_active: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyStatus:
    """Dashboard 策略运行状态。"""

    strategy_name: str
    status: str  # "running" / "paused" / "stopped"
    signal_count_today: int = 0
    last_signal_time: datetime | None = None
    daily_pnl: float = 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class DashboardSnapshot:
    """Dashboard 实时快照值对象。

    聚合账户资产、持仓、风控、策略状态，用于前端实时展示。
    """

    timestamp: datetime
    total_asset: float
    available_cash: float
    frozen_cash: float
    daily_pnl: float
    daily_pnl_ratio: float
    total_market_value: float
    positions: list[PositionSnapshot] = field(default_factory=list)
    risk_status: RiskStatus = field(default_factory=lambda: RiskStatus(
        total_position_ratio=0.0,
        max_concentration=0.0,
        position_count=0,
    ))
    strategies: list[StrategyStatus] = field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class EquityCurvePoint:
    """收益曲线数据点。"""

    date: datetime
    total_asset: float
    daily_pnl: float
    cumulative_return: float
