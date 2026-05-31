import math
from datetime import datetime

from src.domain.portfolio.entities.strategy_performance import StrategyPerformance


class PerformanceTracker:
    """轻量级策略绩效追踪器。

    持续记录每个策略的滚动日收益率，输出 StrategyPerformance。
    用于资金分配引擎的运行时绩效评估。

    Attributes:
        lookback_days: 回看窗口天数。
    """

    def __init__(self, lookback_days: int = 60) -> None:
        self._lookback_days = lookback_days
        # strategy_name -> list[(date, daily_return)]
        self._returns: dict[str, list[tuple[datetime, float]]] = {}

    @property
    def lookback_days(self) -> int:
        return self._lookback_days

    def record_daily_return(self, strategy_name: str, daily_return: float, date: datetime) -> None:
        """记录策略的日收益率。

        Args:
            strategy_name: 策略名称。
            daily_return: 日收益率。
            date: 日期。
        """
        if strategy_name not in self._returns:
            self._returns[strategy_name] = []

        self._returns[strategy_name].append((date, daily_return))

        # 只保留最近 lookback_days * 2 的数据（留余量）
        max_records = self._lookback_days * 2
        if len(self._returns[strategy_name]) > max_records:
            self._returns[strategy_name] = self._returns[strategy_name][-max_records:]

    def get_performance(self, strategy_name: str) -> StrategyPerformance | None:
        """获取指定策略的绩效快照。

        Args:
            strategy_name: 策略名称。

        Returns:
            策略绩效快照，数据不足时返回 None。
        """
        records = self._returns.get(strategy_name)
        if not records or len(records) < 2:
            return None

        # 取最近 lookback_days 的数据
        window = records[-self._lookback_days:]
        returns = [r for _, r in window]
        last_date = window[-1][0]

        return self._calculate_performance(strategy_name, returns, last_date)

    def get_all_performances(self) -> list[StrategyPerformance]:
        """获取所有策略的绩效快照。

        Returns:
            各策略的绩效快照列表（跳过数据不足的策略）。
        """
        result: list[StrategyPerformance] = []
        for name in self._returns:
            perf = self.get_performance(name)
            if perf is not None:
                result.append(perf)
        return result

    def _calculate_performance(
        self,
        strategy_name: str,
        returns: list[float],
        last_date: datetime,
    ) -> StrategyPerformance:
        """从日收益率序列计算绩效指标。"""
        n = len(returns)

        # 累计收益率
        cumulative = 1.0
        for r in returns:
            cumulative *= (1.0 + r)
        total_return = cumulative - 1.0

        # 年化收益率
        if n > 0:
            annualized_return = (cumulative ** (252 / n)) - 1.0
        else:
            annualized_return = 0.0

        # 夏普比率（年化，无风险利率 0）
        mean_return = sum(returns) / n
        if n > 1 and mean_return != 0:
            variance = sum((r - mean_return) ** 2 for r in returns) / (n - 1)
            std = math.sqrt(variance) if variance > 0 else 0.0
            sharpe_ratio = (mean_return / std) * math.sqrt(252) if std > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        # 最大回撤
        peak = 1.0
        equity = 1.0
        max_drawdown = 0.0
        for r in returns:
            equity *= (1.0 + r)
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0.0
            if dd > max_drawdown:
                max_drawdown = dd

        # 胜率
        win_count = sum(1 for r in returns if r > 0)
        win_rate = win_count / n if n > 0 else 0.0

        # 波动率（年化）
        if n > 1:
            variance = sum((r - mean_return) ** 2 for r in returns) / (n - 1)
            volatility = math.sqrt(variance) * math.sqrt(252)
        else:
            volatility = 0.0

        # 盈亏比
        winning = [r for r in returns if r > 0]
        losing = [abs(r) for r in returns if r < 0]
        avg_win = sum(winning) / len(winning) if winning else 0.0
        avg_loss = sum(losing) / len(losing) if losing else 0.0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0

        return StrategyPerformance(
            strategy_name=strategy_name,
            total_return=round(total_return, 6),
            annualized_return=round(annualized_return, 6),
            sharpe_ratio=round(sharpe_ratio, 6),
            max_drawdown=round(max_drawdown, 6),
            win_rate=round(win_rate, 6),
            volatility=round(volatility, 6),
            lookback_days=n,
            updated_at=last_date,
            profit_loss_ratio=round(profit_loss_ratio, 6),
        )
