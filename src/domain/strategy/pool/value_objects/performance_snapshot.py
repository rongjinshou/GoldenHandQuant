from dataclasses import dataclass
from datetime import datetime

from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating


@dataclass(frozen=True, slots=True, kw_only=True)
class PerformanceSnapshot:
    """单次评估快照（不可变值对象）。"""

    evaluated_at: datetime
    period_start: datetime
    period_end: datetime
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    composite_score: float
    rating: StrategyRating
    benchmark_return: float = 0.0
    underperform_weeks: int = 0
