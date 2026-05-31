from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.strategy.pool.value_objects.performance_snapshot import PerformanceSnapshot
from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class RatingEngine:
    """评级引擎 -- 基于回测指标计算策略评级。"""

    def __init__(
        self,
        w_risk: float = 0.40,
        w_drawdown: float = 0.30,
        w_consistency: float = 0.30,
        sharpe_benchmark: float = 2.0,
        max_dd_limit: float = 0.30,
        penalty_per_week: float = 5.0,
    ) -> None:
        self._w_risk = w_risk
        self._w_drawdown = w_drawdown
        self._w_consistency = w_consistency
        self._sharpe_benchmark = sharpe_benchmark
        self._max_dd_limit = max_dd_limit
        self._penalty_per_week = penalty_per_week

    def calculate_score(
        self,
        sharpe_ratio: float,
        max_drawdown: float,
        win_rate: float,
        underperform_weeks: int = 0,
    ) -> float:
        """计算综合得分 (0-100)。"""
        risk_adjusted = _clamp(sharpe_ratio / self._sharpe_benchmark * 100, 0, 100)
        drawdown = _clamp((1 - max_drawdown / self._max_dd_limit) * 100, 0, 100)
        consistency = _clamp(win_rate * 100, 0, 100)
        penalty = underperform_weeks * self._penalty_per_week

        score = (
            self._w_risk * risk_adjusted
            + self._w_drawdown * drawdown
            + self._w_consistency * consistency
            - penalty
        )
        return _clamp(score, 0, 100)

    def calculate_rating(self, score: float) -> StrategyRating:
        """得分转评级。"""
        if score >= 80:
            return StrategyRating.A
        if score >= 60:
            return StrategyRating.B
        if score >= 40:
            return StrategyRating.C
        return StrategyRating.D

    def evaluate(
        self,
        report: BacktestReport,
        benchmark_return: float = 0.0,
        underperform_weeks: int = 0,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> PerformanceSnapshot:
        """基于回测报告生成评估快照。"""
        score = self.calculate_score(
            sharpe_ratio=report.sharpe_ratio,
            max_drawdown=report.max_drawdown,
            win_rate=report.win_rate,
            underperform_weeks=underperform_weeks,
        )
        rating = self.calculate_rating(score)
        now = datetime.now()
        return PerformanceSnapshot(
            evaluated_at=now,
            period_start=period_start or report.start_date,
            period_end=period_end or report.end_date,
            total_return=report.total_return,
            annualized_return=report.annualized_return,
            sharpe_ratio=report.sharpe_ratio,
            max_drawdown=report.max_drawdown,
            win_rate=report.win_rate,
            trade_count=report.trade_count,
            composite_score=score,
            rating=rating,
            benchmark_return=benchmark_return,
            underperform_weeks=underperform_weeks,
        )
