import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.application.backtest_app import BacktestAppService
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.infrastructure.visualization.plotter import BacktestPlotter

class TestBacktestAppServicePlot:
    
    @patch('src.infrastructure.visualization.plotter.BacktestPlotter')
    def test_run_backtest_with_plot_true(self, mock_plotter_cls):
        # Arrange
        # Mock dependencies
        mock_market = MagicMock()
        mock_trade = MagicMock()
        mock_strategy = MagicMock()
        mock_evaluator = MagicMock()
        mock_fetcher = MagicMock()
        
        # Setup mock behavior
        mock_market.get_all_timestamps.return_value = [datetime(2023, 1, 1)]
        mock_market.get_recent_bars.return_value = []
        mock_trade.get_positions.return_value = []
        
        # 正确设置 Asset 的各个属性
        mock_asset = MagicMock()
        mock_asset.total_asset = 100000.0
        mock_asset.available_cash = 100000.0
        mock_asset.frozen_cash = 0.0
        mock_trade.get_asset.return_value = mock_asset
        
        mock_trade.list_orders.return_value = []
        mock_trade.list_trade_records.return_value = []
        mock_strategy.generate_signals.return_value = []
        
        mock_report = BacktestReport(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 1),
            initial_capital=100000.0,
            final_capital=100000.0,
            total_return=0.0,
            annualized_return=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            trade_count=0,
            dates=[datetime(2023, 1, 1)],
            equity_curve=[100000.0],
            daily_returns=[0.0]
        )
        mock_evaluator.evaluate.return_value = mock_report

        service = BacktestAppService(
            market_gateway=mock_market,
            trade_gateway=mock_trade,
            strategy=mock_strategy,
            evaluator=mock_evaluator,
            history_fetcher=mock_fetcher
        )

        # Act
        service.run_backtest(
            symbols=['000001.SZ'],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 1),
            plot=True
        )

        # Assert
        mock_plotter_cls.assert_called_once()
        mock_plotter_instance = mock_plotter_cls.return_value
        mock_plotter_instance.plot.assert_called_once_with(mock_report)

    @patch('src.infrastructure.visualization.plotter.BacktestPlotter')
    def test_run_backtest_with_plot_false(self, mock_plotter_cls):
        # Arrange
        # Mock dependencies
        mock_market = MagicMock()
        mock_trade = MagicMock()
        mock_strategy = MagicMock()
        mock_evaluator = MagicMock()
        
        mock_market.get_all_timestamps.return_value = [datetime(2023, 1, 1)]
        
        mock_asset = MagicMock()
        mock_asset.total_asset = 100000.0
        mock_asset.available_cash = 100000.0
        mock_asset.frozen_cash = 0.0
        mock_trade.get_asset.return_value = mock_asset
        
        mock_trade.list_orders.return_value = []
        mock_trade.list_trade_records.return_value = []
        mock_evaluator.evaluate.return_value = MagicMock()

        service = BacktestAppService(
            market_gateway=mock_market,
            trade_gateway=mock_trade,
            strategy=mock_strategy,
            evaluator=mock_evaluator
        )

        # Act
        service.run_backtest(
            symbols=['000001.SZ'],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 1),
            plot=False
        )

        # Assert
        mock_plotter_cls.assert_not_called()
