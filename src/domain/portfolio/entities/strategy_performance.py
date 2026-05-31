from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyPerformance:
    """策略绩效快照，用于分配决策。

    Attributes:
        strategy_name: 策略名称。
        total_return: 累计收益率。
        annualized_return: 年化收益率。
        sharpe_ratio: 夏普比率。
        max_drawdown: 最大回撤。
        win_rate: 胜率。
        volatility: 日收益率标准差 (年化)。
        lookback_days: 回看窗口天数。
        updated_at: 更新时间。
        profit_loss_ratio: 盈亏比（用于凯利公式）。
    """

    strategy_name: str
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    volatility: float
    lookback_days: int
    updated_at: datetime
    profit_loss_ratio: float = 0.0
