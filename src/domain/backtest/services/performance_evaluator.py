from datetime import datetime
from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.domain.backtest.value_objects.trade_record import TradeRecord
from src.domain.trade.value_objects.order_direction import OrderDirection


class PerformanceEvaluator:
    """回测绩效评估器。

    仅负责聚合 DailySnapshot → BacktestReport 的基础指标，
    风险调整收益指标（sharpe_ratio、sortino_ratio、calmar_ratio）
    由 BacktestReport 的 @property 惰性计算。
    """

    def evaluate(
        self,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        snapshots: list[DailySnapshot],
        trades: list[TradeRecord],
    ) -> BacktestReport:
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
                profit_loss_ratio=0.0,
                trade_count=len(trades),
                trades=trades,
                snapshots=snapshots,
            )

        final_capital = snapshots[-1].total_asset
        total_return = (final_capital - initial_capital) / initial_capital

        days = (end_date - start_date).days
        if days > 0:
            annualized_return = (1 + total_return) ** (365 / days) - 1
        else:
            annualized_return = 0.0

        # 最大回撤
        max_drawdown = 0.0
        peak = initial_capital
        for snap in snapshots:
            if snap.total_asset > peak:
                peak = snap.total_asset
            drawdown = (peak - snap.total_asset) / peak if peak > 0 else 0.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 胜率与盈亏比
        sell_trades = [t for t in trades if t.direction == OrderDirection.SELL]
        win_count = sum(1 for t in sell_trades if t.realized_pnl > 0)
        win_rate = win_count / len(sell_trades) if sell_trades else 0.0

        winning_trades = [t for t in sell_trades if t.realized_pnl > 0]
        losing_trades = [t for t in sell_trades if t.realized_pnl <= 0]
        avg_win = sum(t.realized_pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0.0
        avg_loss = abs(sum(t.realized_pnl for t in losing_trades)) / len(losing_trades) if losing_trades else 0.0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0

        dates = [s.date for s in snapshots]
        equity_curve = [s.total_asset for s in snapshots]
        daily_returns = [s.return_rate for s in snapshots]

        return BacktestReport(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_loss_ratio=profit_loss_ratio,
            trade_count=len(trades),
            trades=trades,
            snapshots=snapshots,
            dates=dates,
            equity_curve=equity_curve,
            daily_returns=daily_returns,
        )
