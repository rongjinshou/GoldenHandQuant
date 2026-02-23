from datetime import datetime
from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.domain.backtest.value_objects.trade_record import TradeRecord
from src.domain.trade.value_objects.order_direction import OrderDirection

class PerformanceEvaluator:
    """回测绩效评估器。"""

    def evaluate(
        self,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        snapshots: list[DailySnapshot],
        trades: list[TradeRecord],
    ) -> BacktestReport:
        """评估回测结果。

        Args:
            start_date: 开始日期。
            end_date: 结束日期。
            initial_capital: 初始资金。
            snapshots: 每日快照列表。
            trades: 交易记录列表。

        Returns:
            BacktestReport: 回测报告。
        """
        if not snapshots:
            return BacktestReport(
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                final_capital=initial_capital,
                total_return=0.0,
                annualized_return=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                trade_count=len(trades),
                trades=trades,
                snapshots=snapshots,
            )

        final_capital = snapshots[-1].total_asset
        total_return = (final_capital - initial_capital) / initial_capital

        # 计算年化收益率 (简单估算: 按 250 个交易日)
        days = (end_date - start_date).days
        if days > 0:
            annualized_return = (1 + total_return) ** (365 / days) - 1
        else:
            annualized_return = 0.0

        # 计算最大回撤
        max_drawdown = 0.0
        peak = initial_capital
        for snap in snapshots:
            if snap.total_asset > peak:
                peak = snap.total_asset
            drawdown = (peak - snap.total_asset) / peak if peak > 0 else 0.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 计算胜率 (基于平仓盈亏)
        sell_trades = [t for t in trades if t.direction == OrderDirection.SELL]
        win_count = sum(1 for t in sell_trades if t.realized_pnl > 0)
        win_rate = win_count / len(sell_trades) if sell_trades else 0.0

        return BacktestReport(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            trade_count=len(trades),
            trades=trades,
            snapshots=snapshots,
        )
