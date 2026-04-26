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
