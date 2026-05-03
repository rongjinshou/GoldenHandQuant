from datetime import datetime
from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.domain.backtest.value_objects.trade_record import TradeRecord
from src.domain.trade.value_objects.order_direction import OrderDirection

def test_turnover_rate_basic():
    snapshots = [
        DailySnapshot(date=datetime(2024, 6, 10), total_asset=100000, available_cash=50000, market_value=50000, pnl=0, return_rate=0),
        DailySnapshot(date=datetime(2024, 6, 11), total_asset=101000, available_cash=40000, market_value=61000, pnl=1000, return_rate=0.01),
    ]
    trades = [
        TradeRecord(symbol="A", direction=OrderDirection.BUY, execute_at=datetime(2024, 6, 11), price=10.0, volume=1000),
    ]
    report = BacktestReport(
        start_date=datetime(2024, 6, 10), end_date=datetime(2024, 6, 11),
        initial_capital=100000, final_capital=101000,
        total_return=0.01, annualized_return=0.1, max_drawdown=0.0,
        win_rate=1.0, profit_loss_ratio=1.0, trade_count=1,
        snapshots=snapshots, trades=trades,
        dates=[s.date for s in snapshots],
        equity_curve=[s.total_asset for s in snapshots],
        daily_returns=[s.return_rate for s in snapshots],
    )
    # turnover = sum(trade_value) / avg_equity
    # trade_value = 1000 * 10 = 10000
    # avg_equity = (100000 + 101000) / 2 = 100500
    # daily_turnover = 10000 / 100500 ≈ 0.0995
    assert report.turnover_rate > 0
    assert report.turnover_rate < 1.0
