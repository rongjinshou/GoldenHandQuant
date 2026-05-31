import logging
import math
from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.backtest.entities.comparison_report import (
    ComparisonReport,
    StrategyMetricRow,
)

logger = logging.getLogger(__name__)


class ComparisonReportService:
    """多策略对比报告领域服务。

    纯 Python 实现，不依赖任何第三方库。
    """

    def build_comparison(self, reports: list[BacktestReport]) -> ComparisonReport:
        """从多个 BacktestReport 构建对比报告。"""
        metric_table = self._extract_metrics(reports)
        aligned_dates, aligned_curves = self._align_equity_curves(reports)
        corr_matrix = self._compute_correlation_matrix(reports, aligned_dates)

        best_sharpe = max(reports, key=lambda r: r.sharpe_ratio).strategy_name
        best_calmar = max(reports, key=lambda r: r.calmar_ratio).strategy_name
        combo = self._recommend_combo(reports, corr_matrix)

        return ComparisonReport(
            reports=reports,
            metric_table=metric_table,
            correlation_matrix=corr_matrix,
            aligned_dates=aligned_dates,
            aligned_equity_curves=aligned_curves,
            best_by_sharpe=best_sharpe,
            best_by_calmar=best_calmar,
            recommended_combo=combo,
        )

    def _extract_metrics(self, reports: list[BacktestReport]) -> list[StrategyMetricRow]:
        """从每个 BacktestReport 提取指标，构造 StrategyMetricRow。"""
        return [
            StrategyMetricRow(
                strategy_name=r.strategy_name,
                total_return=r.total_return,
                annualized_return=r.annualized_return,
                max_drawdown=r.max_drawdown,
                sharpe_ratio=r.sharpe_ratio,
                sortino_ratio=r.sortino_ratio,
                calmar_ratio=r.calmar_ratio,
                win_rate=r.win_rate,
                trade_count=r.trade_count,
                turnover_rate=r.turnover_rate,
            )
            for r in reports
        ]

    def _align_equity_curves(
        self, reports: list[BacktestReport]
    ) -> tuple[list[datetime], dict[str, list[float]]]:
        """取所有报告 dates 的交集，将各策略 equity_curve 按公共日期对齐并归一化。"""
        if not reports:
            return [], {}

        # 构建每个策略的 date->equity 映射
        date_equity_maps: list[dict[datetime, float]] = []
        for r in reports:
            m: dict[datetime, float] = {}
            for i, d in enumerate(r.dates):
                if i < len(r.equity_curve):
                    m[d] = r.equity_curve[i]
            date_equity_maps.append(m)

        # 取日期交集
        common_dates = set(date_equity_maps[0].keys())
        for m in date_equity_maps[1:]:
            common_dates &= set(m.keys())
        aligned_dates = sorted(common_dates)

        # 对齐并归一化到初始值 = 1.0
        aligned_curves: dict[str, list[float]] = {}
        for r, eq_map in zip(reports, date_equity_maps):
            curve = [eq_map[d] for d in aligned_dates]
            if curve and curve[0] != 0:
                initial = curve[0]
                curve = [v / initial for v in curve]
            aligned_curves[r.strategy_name] = curve

        return aligned_dates, aligned_curves

    def _compute_correlation_matrix(
        self, reports: list[BacktestReport], aligned_dates: list[datetime]
    ) -> list[list[float]]:
        """纯 Python 皮尔逊相关系数矩阵。仅使用对齐日期上的 daily_returns。"""
        n = len(reports)
        if n <= 1:
            return [[1.0]] if n == 1 else []

        if len(aligned_dates) < 30:
            logger.warning(
                "Only %d common dates available. "
                "Correlation results may be unreliable (need >= 30).",
                len(aligned_dates),
            )

        # 构建每个策略在对齐日期上的日收益率序列
        aligned_returns: list[list[float]] = []
        for r in reports:
            date_ret_map: dict[datetime, float] = {}
            for i, d in enumerate(r.dates):
                if i < len(r.daily_returns):
                    date_ret_map[d] = r.daily_returns[i]
            rets = [date_ret_map.get(d, 0.0) for d in aligned_dates]
            aligned_returns.append(rets)

        # 计算 NxN 相关性矩阵
        matrix: list[list[float]] = []
        for i in range(n):
            row: list[float] = []
            for j in range(n):
                if i == j:
                    row.append(1.0)
                else:
                    row.append(self._pearson(aligned_returns[i], aligned_returns[j]))
            matrix.append(row)

        return matrix

    @staticmethod
    def _pearson(x: list[float], y: list[float]) -> float:
        """计算皮尔逊相关系数。"""
        n = len(x)
        if n < 2 or n != len(y):
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)

        denom = math.sqrt(var_x * var_y)
        if denom == 0:
            return 0.0
        return cov / denom

    def _recommend_combo(
        self, reports: list[BacktestReport], corr_matrix: list[list[float]]
    ) -> list[str]:
        """推荐低相关策略组合。

        1. 找相关系数 < 0.5 的策略对。
        2. 从中选 Sharpe 之和最高的一组。
        3. 若无低相关对，返回 Sharpe 最高的单策略。
        """
        if len(reports) <= 1:
            return [reports[0].strategy_name] if reports else []

        sharpe_map = {r.strategy_name: r.sharpe_ratio for r in reports}
        names = [r.strategy_name for r in reports]

        best_pair: list[str] = []
        best_sharpe_sum = -math.inf

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                if corr_matrix[i][j] < 0.5:
                    sharpe_sum = sharpe_map[names[i]] + sharpe_map[names[j]]
                    if sharpe_sum > best_sharpe_sum:
                        best_sharpe_sum = sharpe_sum
                        best_pair = [names[i], names[j]]

        if best_pair:
            return best_pair

        # 无低相关对，返回 Sharpe 最高的单策略
        best = max(reports, key=lambda r: r.sharpe_ratio)
        return [best.strategy_name]
