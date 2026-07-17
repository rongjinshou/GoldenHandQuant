"""ComparisonReportService 单元测试。"""
from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.backtest.services.comparison_report_service import ComparisonReportService


def _make_report(
    name: str,
    dates: list[datetime],
    equity_curve: list[float],
    daily_returns: list[float],
    initial_capital: float = 100_000.0,
    annualized_return: float = 0.15,
    max_drawdown: float = 0.10,
    win_rate: float = 0.55,
    trade_count: int = 20,
) -> BacktestReport:
    """构造测试用 BacktestReport。"""
    return BacktestReport(
        start_date=dates[0] if dates else datetime(2024, 1, 1),
        end_date=dates[-1] if dates else datetime(2024, 12, 31),
        initial_capital=initial_capital,
        final_capital=equity_curve[-1] if equity_curve else initial_capital,
        total_return=(equity_curve[-1] / initial_capital - 1) if equity_curve else 0.0,
        annualized_return=annualized_return,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        profit_loss_ratio=1.5,
        trade_count=trade_count,
        dates=dates,
        equity_curve=equity_curve,
        daily_returns=daily_returns,
        strategy_name=name,
    )


def _make_dates(n: int, start: datetime = datetime(2024, 1, 2)) -> list[datetime]:
    """生成 n 个交易日日期列表（跳过周末简化处理）。"""
    dates = []
    d = start
    for _ in range(n):
        dates.append(d)
        d = datetime(d.year, d.month, d.day + 1) if d.day < 28 else datetime(d.year, d.month + 1, 1)
    return dates


class TestComparisonReportService:
    def test_build_comparison_two_strategies(self):
        """两个策略，metric_table 有 2 行，corr_matrix 为 2x2。"""
        svc = ComparisonReportService()
        dates = _make_dates(50)
        r1 = _make_report("A", dates, [100_000 + i * 200 for i in range(50)],
                          [0.002] * 50, annualized_return=0.15)
        r2 = _make_report("B", dates, [100_000 + i * 100 for i in range(50)],
                          [0.001] * 50, annualized_return=0.08)

        report = svc.build_comparison([r1, r2])

        assert len(report.metric_table) == 2
        assert len(report.correlation_matrix) == 2
        assert len(report.correlation_matrix[0]) == 2
        assert report.metric_table[0].strategy_name == "A"
        assert report.metric_table[1].strategy_name == "B"

    def test_build_comparison_three_strategies(self):
        """三个策略，metric_table 有 3 行，corr_matrix 为 3x3。"""
        svc = ComparisonReportService()
        dates = _make_dates(60)
        r1 = _make_report("A", dates, [100_000 + i * 200 for i in range(60)],
                          [0.002] * 60, annualized_return=0.20)
        r2 = _make_report("B", dates, [100_000 + i * 150 for i in range(60)],
                          [0.0015] * 60, annualized_return=0.12)
        r3 = _make_report("C", dates, [100_000 + i * 100 for i in range(60)],
                          [0.001] * 60, annualized_return=0.08)

        report = svc.build_comparison([r1, r2, r3])

        assert len(report.metric_table) == 3
        assert len(report.correlation_matrix) == 3
        assert all(len(row) == 3 for row in report.correlation_matrix)

    def test_correlation_perfect_positive(self):
        """两个完全正相关策略，pearson 应约等于 1.0。"""
        svc = ComparisonReportService()
        dates = _make_dates(50)
        rets = [0.01, -0.005, 0.02, -0.01, 0.015] * 10
        r1 = _make_report("A", dates, [100_000] * 50, rets)
        r2 = _make_report("B", dates, [100_000] * 50, rets[:])

        report = svc.build_comparison([r1, r2])

        assert abs(report.correlation_matrix[0][1] - 1.0) < 0.001

    def test_correlation_perfect_negative(self):
        """两个完全负相关策略，pearson 应约等于 -1.0。"""
        svc = ComparisonReportService()
        dates = _make_dates(50)
        rets_a = [0.01, -0.005, 0.02, -0.01, 0.015] * 10
        rets_b = [-r for r in rets_a]
        r1 = _make_report("A", dates, [100_000] * 50, rets_a)
        r2 = _make_report("B", dates, [100_000] * 50, rets_b)

        report = svc.build_comparison([r1, r2])

        assert abs(report.correlation_matrix[0][1] - (-1.0)) < 0.001

    def test_correlation_uncorrelated(self):
        """两个不相关策略，pearson 应约等于 0.0。"""
        svc = ComparisonReportService()
        dates = _make_dates(100)
        # 构造正交序列: x 单调递增, y = 0
        rets_a = [0.001 * (i % 2 == 0) - 0.001 * (i % 2 != 0) for i in range(100)]
        rets_b = [0.0] * 100
        r1 = _make_report("A", dates, [100_000] * 100, rets_a)
        r2 = _make_report("B", dates, [100_000] * 100, rets_b)

        report = svc.build_comparison([r1, r2])

        # B 的 daily_returns 全为 0，std 为 0，pearson 应为 0.0
        assert abs(report.correlation_matrix[0][1]) < 0.001

    def test_align_equity_curves_different_dates(self):
        """策略 A 有 100 天，策略 B 有 80 天，对齐后长度 = 交集天数。"""
        svc = ComparisonReportService()
        dates_a = _make_dates(100)
        dates_b = dates_a[20:]  # 80 天，偏移 20 天

        r1 = _make_report("A", dates_a, [100_000 + i * 100 for i in range(100)],
                          [0.001] * 100)
        r2 = _make_report("B", dates_b, [100_000 + i * 100 for i in range(80)],
                          [0.001] * 80)

        report = svc.build_comparison([r1, r2])

        assert len(report.aligned_dates) == 80
        assert len(report.aligned_equity_curves["A"]) == 80
        assert len(report.aligned_equity_curves["B"]) == 80

    def test_recommend_low_correlation_pair(self):
        """三个策略，A-B 低相关且 Sharpe 最高，应推荐 A+B。"""
        svc = ComparisonReportService()
        dates = _make_dates(60)
        # A 和 B 负相关
        rets_a = [0.01, -0.01] * 30
        rets_b = [-0.01, 0.01] * 30
        # C 和 A 正相关
        rets_c = [0.01, -0.01] * 30

        r1 = _make_report("A", dates, [100_000] * 60, rets_a, annualized_return=0.20)
        r2 = _make_report("B", dates, [100_000] * 60, rets_b, annualized_return=0.15)
        r3 = _make_report("C", dates, [100_000] * 60, rets_c, annualized_return=0.10)

        report = svc.build_comparison([r1, r2, r3])

        # A 和 C 正相关(1.0)，A 和 B 负相关(-1.0)，B 和 C 负相关(-1.0)
        # 低相关对: A+B(-1.0), B+C(-1.0)
        # A+B Sharpe 和 > B+C Sharpe 和（A 的 annualized 更高）
        assert "A" in report.recommended_combo
        assert "B" in report.recommended_combo

    def test_recommend_single_when_all_correlated(self):
        """所有策略高相关，应推荐 Sharpe 最高的单策略。"""
        svc = ComparisonReportService()
        dates = _make_dates(60)
        rets = [0.01, -0.005, 0.02, -0.01, 0.015, -0.008] * 10

        r1 = _make_report("A", dates, [100_000] * 60, rets, annualized_return=0.20)
        r2 = _make_report("B", dates, [100_000] * 60, rets, annualized_return=0.10)

        report = svc.build_comparison([r1, r2])

        # 完全正相关，无低相关对
        assert report.recommended_combo == ["A"]

    def test_insufficient_data_warning(self, caplog):
        """公共日期 < 30 时应记录警告日志。"""
        import logging

        svc = ComparisonReportService()
        dates = _make_dates(20)
        r1 = _make_report("A", dates, [100_000] * 20, [0.001] * 20)
        r2 = _make_report("B", dates, [100_000] * 20, [0.001] * 20)

        with caplog.at_level(logging.WARNING):
            svc.build_comparison([r1, r2])

        assert "unreliable" in caplog.text  # 因 Spec 1 正确性修复更新预期

    def test_single_strategy_no_correlation(self):
        """只有一个策略，corr_matrix 为 [[1.0]]，combo 为该策略。"""
        svc = ComparisonReportService()
        dates = _make_dates(50)
        r1 = _make_report("Solo", dates, [100_000 + i * 100 for i in range(50)],
                          [0.001] * 50)

        report = svc.build_comparison([r1])

        assert len(report.metric_table) == 1
        assert report.correlation_matrix == [[1.0]]
        assert report.recommended_combo == ["Solo"]
        assert report.best_by_sharpe == "Solo"
