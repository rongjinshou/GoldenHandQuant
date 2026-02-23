from dataclasses import dataclass, field
from datetime import datetime
from src.domain.backtest.value_objects.trade_record import TradeRecord
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot

@dataclass(slots=True, kw_only=True)
class BacktestReport:
    """回测结果报告实体。

    Attributes:
        start_date: 回测开始日期。
        end_date: 回测结束日期。
        initial_capital: 初始资金。
        final_capital: 最终资金。
        total_return: 总收益率。
        annualized_return: 年化收益率。
        max_drawdown: 最大回撤。
        win_rate: 胜率 (盈利交易次数 / 总交易次数)。
        trade_count: 总交易次数。
        trades: 交易记录列表。
        snapshots: 每日快照列表。
    """
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    annualized_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    trades: list[TradeRecord] = field(default_factory=list)
    snapshots: list[DailySnapshot] = field(default_factory=list)
