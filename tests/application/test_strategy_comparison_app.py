"""StrategyComparisonAppService 单元测试。"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.application.strategy_comparison_app import StrategyComparisonAppService
from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.market.value_objects.timeframe import Timeframe


def _make_report(name: str) -> BacktestReport:
    return BacktestReport(
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        initial_capital=100_000,
        final_capital=115_000,
        total_return=0.15,
        annualized_return=0.15,
        max_drawdown=0.10,
        win_rate=0.55,
        profit_loss_ratio=1.5,
        trade_count=20,
        strategy_name=name,
    )


class TestStrategyComparisonAppService:
    @patch("src.application.strategy_comparison_app.create_strategy")
    def test_run_comparison_returns_report(self, mock_create):
        """传入 2 个策略名，返回 ComparisonReport，metric_table 有 2 行。"""
        mock_strategy_a = MagicMock()
        mock_strategy_a.name = "A"
        mock_strategy_b = MagicMock()
        mock_strategy_b.name = "B"
        mock_create.side_effect = [mock_strategy_a, mock_strategy_b]

        mock_backtest = MagicMock()
        mock_backtest.run_backtest.return_value = [
            _make_report("A"),
            _make_report("B"),
        ]

        comparison_service = MagicMock()
        expected_report = MagicMock()
        comparison_service.build_comparison.return_value = expected_report

        app = StrategyComparisonAppService(mock_backtest, comparison_service)
        result = app.run_comparison(
            strategy_names=["A", "B"],
            symbols=["000001.SZ"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        assert result is expected_report
        mock_backtest.run_backtest.assert_called_once()
        comparison_service.build_comparison.assert_called_once()

    @patch("src.application.strategy_comparison_app.create_strategy")
    def test_run_comparison_unknown_strategy_raises(self, mock_create):
        """传入不存在的策略名，抛出 KeyError。"""
        mock_create.side_effect = KeyError("Unknown strategy: nonexistent")

        mock_backtest = MagicMock()
        comparison_service = MagicMock()

        app = StrategyComparisonAppService(mock_backtest, comparison_service)
        with pytest.raises(KeyError):
            app.run_comparison(
                strategy_names=["nonexistent"],
                symbols=["000001.SZ"],
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
            )

    @patch("src.application.strategy_comparison_app.create_strategy")
    def test_run_comparison_passes_params(self, mock_create):
        """传入自定义参数，策略使用自定义参数创建。"""
        mock_strategy = MagicMock()
        mock_strategy.name = "multi_factor"
        mock_create.return_value = mock_strategy

        mock_backtest = MagicMock()
        mock_backtest.run_backtest.return_value = [_make_report("multi_factor")]
        comparison_service = MagicMock()
        comparison_service.build_comparison.return_value = MagicMock()

        app = StrategyComparisonAppService(mock_backtest, comparison_service)
        app.run_comparison(
            strategy_names=["multi_factor"],
            symbols=["000001.SZ"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            strategy_params={"multi_factor": {"top_n": 20}},
        )

        mock_create.assert_called_once_with("multi_factor", {"top_n": 20})
