import math
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.domain.backtest.value_objects.trade_record import TradeRecord


@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestReport:
    """回测结果报告实体（充血模型）。

    所有风险调整收益指标均为惰性计算的 @property，
    避免重复计算，同时保持不可变性。
    """
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    annualized_return: float
    max_drawdown: float
    win_rate: float
    profit_loss_ratio: float
    trade_count: int
    trades: list[TradeRecord] = field(default_factory=list)
    snapshots: list[DailySnapshot] = field(default_factory=list)
    dates: list[datetime] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    daily_returns: list[float] = field(default_factory=list)

    @property
    def turnover_rate(self) -> float:
        """日均换手率 = 日均交易额 / 日均总资产。"""
        if not self.trades or not self.snapshots:
            return 0.0
        total_trade_value = sum(t.price * t.volume for t in self.trades)
        avg_equity = sum(s.total_asset for s in self.snapshots) / len(self.snapshots)
        if avg_equity <= 0:
            return 0.0
        return (total_trade_value / avg_equity) / len(self.snapshots)

    @property
    def sharpe_ratio(self) -> float:
        """夏普比率（年化，无风险利率假设为 0）。"""
        if len(self.daily_returns) < 2:
            return 0.0
        mean_return = sum(self.daily_returns) / len(self.daily_returns)
        if mean_return == 0:
            return 0.0
        variance = sum((r - mean_return) ** 2 for r in self.daily_returns) / (len(self.daily_returns) - 1)
        std = math.sqrt(variance) if variance > 0 else 0.0
        if std == 0:
            return 0.0
        return (mean_return / std) * math.sqrt(252)

    @property
    def sortino_ratio(self) -> float:
        """索提诺比率（仅用下行标准差）。"""
        if len(self.daily_returns) < 2:
            return 0.0
        downside = [min(r, 0) for r in self.daily_returns]
        if not downside:
            return 0.0
        mean_downside = sum(downside) / len(downside)
        variance = sum((r - mean_downside) ** 2 for r in downside) / (len(downside) - 1)
        std = math.sqrt(variance) if variance > 0 else 0.0
        if std == 0:
            return 0.0
        mean_return = sum(self.daily_returns) / len(self.daily_returns)
        return (mean_return / std) * math.sqrt(252)

    @property
    def calmar_ratio(self) -> float:
        """卡尔玛比率 = 年化收益率 / 最大回撤（绝对值）。"""
        if self.max_drawdown <= 0:
            return 0.0
        return self.annualized_return / self.max_drawdown
