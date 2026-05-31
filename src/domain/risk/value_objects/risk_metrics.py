from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class RiskMetrics:
    """风险指标快照。"""

    total_position_ratio: float  # market_value / total_asset
    max_concentration: float  # max(单只市值) / total_asset
    position_count: int
    today_drawdown: float = 0.0  # 当日回撤
