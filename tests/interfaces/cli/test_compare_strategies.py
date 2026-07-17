"""CLI compare_strategies 集成测试。"""
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.application.strategy_comparison_app import StrategyComparisonAppService
from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.backtest.services.comparison_report_service import ComparisonReportService


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


class TestCompareStrategies:
    def test_compare_two_strategies_returns_report(self):
        """使用 mock 数据对比两个策略，返回 ComparisonReport，metric_table 有 2 行。"""
        mock_backtest = MagicMock()
        mock_backtest.run_backtest.return_value = [
            _make_report("dual_ma"),
            _make_report("micro_value"),
        ]

        comparison_service = ComparisonReportService()
        app = StrategyComparisonAppService(mock_backtest, comparison_service)

        report = app.run_comparison(
            strategy_names=["dual_ma", "micro_value"],
            symbols=["000001.SZ"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        assert len(report.metric_table) == 2
        assert report.metric_table[0].strategy_name == "dual_ma"
        assert report.metric_table[1].strategy_name == "micro_value"
        assert len(report.correlation_matrix) == 2
        assert report.best_by_sharpe in ("dual_ma", "micro_value")

    @patch("src.application.strategy_comparison_app.create_strategy")
    def test_compare_prints_table(self, mock_create, capsys):
        """运行 ComparisonRichPrinter 输出包含策略名称。"""
        from src.infrastructure.visualization.comparison_printer import ComparisonRichPrinter

        mock_s1 = MagicMock()
        mock_s1.name = "alpha"
        mock_s2 = MagicMock()
        mock_s2.name = "beta"
        mock_create.side_effect = [mock_s1, mock_s2]

        mock_backtest = MagicMock()
        mock_backtest.run_backtest.return_value = [
            _make_report("alpha"),
            _make_report("beta"),
        ]

        comparison_service = ComparisonReportService()
        app = StrategyComparisonAppService(mock_backtest, comparison_service)
        report = app.run_comparison(
            strategy_names=["alpha", "beta"],
            symbols=["000001.SZ"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        ComparisonRichPrinter().print(report)

        captured = capsys.readouterr()
        assert "alpha" in captured.out
        assert "beta" in captured.out
        assert "COMPARISON" in captured.out.upper()
