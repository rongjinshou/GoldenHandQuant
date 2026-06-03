from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport


def _report(daily_returns):
    return BacktestReport(
        start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 5),
        initial_capital=1e6, final_capital=1e6, total_return=0.0,
        annualized_return=0.0, max_drawdown=0.0, win_rate=0.0,
        profit_loss_ratio=0.0, trade_count=0, daily_returns=daily_returns,
    )


def test_sortino_uses_standard_downside_deviation():
    # daily_returns = [-0.01, 0.02, -0.03, 0.01]
    # mean = -0.0025
    # downside_dev = sqrt((0.0001 + 0 + 0.0009 + 0)/4) = sqrt(0.00025) = 0.0158113883
    # sortino = (-0.0025 / 0.0158113883) * sqrt(252) = -2.5098
    report = _report([-0.01, 0.02, -0.03, 0.01])
    assert abs(report.sortino_ratio - (-2.5098)) < 0.01


def test_sortino_zero_when_no_downside():
    report = _report([0.01, 0.02, 0.03])
    assert report.sortino_ratio == 0.0
