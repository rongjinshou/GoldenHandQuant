import pytest
from datetime import datetime
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.domain.backtest.value_objects.trade_record import TradeRecord

class TestPerformanceEvaluator:
    def test_evaluate_should_populate_curve_data(self):
        # Arrange
        evaluator = PerformanceEvaluator()
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 5)
        initial_capital = 100000.0
        
        snapshots = [
            DailySnapshot(
                date=datetime(2023, 1, 1),
                total_asset=101000.0,
                available_cash=50000.0,
                market_value=51000.0,
                pnl=1000.0,
                return_rate=0.01
            ),
            DailySnapshot(
                date=datetime(2023, 1, 2),
                total_asset=102000.0,
                available_cash=50000.0,
                market_value=52000.0,
                pnl=1000.0,
                return_rate=0.0099
            ),
        ]
        
        trades = []

        # Act
        report = evaluator.evaluate(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            snapshots=snapshots,
            trades=trades
        )

        # Assert
        assert len(report.dates) == 2
        assert report.dates[0] == datetime(2023, 1, 1)
        assert report.dates[1] == datetime(2023, 1, 2)
        
        assert len(report.equity_curve) == 2
        assert report.equity_curve[0] == 101000.0
        assert report.equity_curve[1] == 102000.0
        
        assert len(report.daily_returns) == 2
        assert report.daily_returns[0] == 0.01
        assert report.daily_returns[1] == 0.0099


def test_backtest_report_sharpe_ratio():
    from src.domain.backtest.entities.backtest_report import BacktestReport
    from datetime import datetime

    report = BacktestReport(
        start_date=datetime(2024, 1, 2),
        end_date=datetime(2024, 1, 10),
        initial_capital=100000,
        final_capital=110000,
        total_return=0.10,
        annualized_return=0.15,
        max_drawdown=0.05,
        win_rate=0.55,
        profit_loss_ratio=1.5,
        trade_count=20,
        daily_returns=[0.01, -0.005, 0.02, -0.01, 0.015, 0.005, -0.002, 0.008],
    )
    assert report.sharpe_ratio > 0
    assert isinstance(report.sharpe_ratio, float)


def test_backtest_report_sortino_excludes_upside_volatility():
    from src.domain.backtest.entities.backtest_report import BacktestReport
    from datetime import datetime

    report = BacktestReport(
        start_date=datetime(2024, 1, 2),
        end_date=datetime(2024, 1, 10),
        initial_capital=100000,
        final_capital=110000,
        total_return=0.10,
        annualized_return=0.18,
        max_drawdown=0.03,
        win_rate=0.6,
        profit_loss_ratio=2.0,
        trade_count=10,
        daily_returns=[0.05, 0.03, -0.01, 0.04, -0.005, 0.02, -0.01, 0.03],
    )
    assert report.sortino_ratio > 0


def test_backtest_report_calmar_ratio_zero_drawdown():
    from src.domain.backtest.entities.backtest_report import BacktestReport
    from datetime import datetime

    report = BacktestReport(
        start_date=datetime(2024, 1, 2),
        end_date=datetime(2024, 1, 10),
        initial_capital=100000,
        final_capital=110000,
        total_return=0.10,
        annualized_return=0.15,
        max_drawdown=0.0,
        win_rate=1.0,
        profit_loss_ratio=0.0,
        trade_count=10,
        daily_returns=[0.01] * 8,
    )
    assert report.calmar_ratio == 0.0


def test_backtest_report_sharpe_empty_returns():
    from src.domain.backtest.entities.backtest_report import BacktestReport
    from datetime import datetime

    report = BacktestReport(
        start_date=datetime(2024, 1, 2),
        end_date=datetime(2024, 1, 10),
        initial_capital=100000,
        final_capital=100000,
        total_return=0.0,
        annualized_return=0.0,
        max_drawdown=0.0,
        win_rate=0.0,
        profit_loss_ratio=0.0,
        trade_count=0,
        daily_returns=[],
    )
    assert report.sharpe_ratio == 0.0
    assert report.sortino_ratio == 0.0


def test_evaluate_calculates_max_drawdown_correctly():
    evaluator = PerformanceEvaluator()
    snapshots = [
        DailySnapshot(date=datetime(2024, 1, 2), total_asset=100000, available_cash=0,
                      market_value=100000, pnl=0, return_rate=0),
        DailySnapshot(date=datetime(2024, 1, 3), total_asset=120000, available_cash=0,
                      market_value=120000, pnl=20000, return_rate=0.2),
        DailySnapshot(date=datetime(2024, 1, 4), total_asset=80000, available_cash=0,
                      market_value=80000, pnl=-40000, return_rate=-0.333),
    ]
    report = evaluator.evaluate(
        start_date=datetime(2024, 1, 2), end_date=datetime(2024, 1, 4),
        initial_capital=100000, snapshots=snapshots, trades=[],
    )
    assert abs(report.max_drawdown - 1/3) < 0.01


def test_evaluate_empty_snapshots_returns_default_report():
    evaluator = PerformanceEvaluator()
    report = evaluator.evaluate(
        start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 10),
        initial_capital=100000, snapshots=[], trades=[],
    )
    assert report.final_capital == 100000
    assert report.total_return == 0.0
    assert report.win_rate == 0.0
