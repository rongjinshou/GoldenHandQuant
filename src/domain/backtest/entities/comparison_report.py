from dataclasses import dataclass
from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyMetricRow:
    """单策略的指标摘要行。"""
    strategy_name: str
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    win_rate: float
    trade_count: int
    turnover_rate: float


@dataclass(frozen=True, slots=True, kw_only=True)
class ComparisonReport:
    """多策略对比报告实体。

    Attributes:
        reports: 各策略的 BacktestReport 列表。
        metric_table: 指标对比表（每行一个策略）。
        correlation_matrix: 策略日收益率相关性矩阵。
        aligned_dates: 对齐后的公共日期序列。
        aligned_equity_curves: 对齐后的各策略净值曲线（归一化到 1.0）。
        best_by_sharpe: 夏普最高的策略名称。
        best_by_calmar: Calmar 最高的策略名称。
        recommended_combo: 推荐的低相关策略组合。
    """
    reports: list[BacktestReport]
    metric_table: list[StrategyMetricRow]
    correlation_matrix: list[list[float]]
    aligned_dates: list[datetime]
    aligned_equity_curves: dict[str, list[float]]
    best_by_sharpe: str
    best_by_calmar: str
    recommended_combo: list[str]
