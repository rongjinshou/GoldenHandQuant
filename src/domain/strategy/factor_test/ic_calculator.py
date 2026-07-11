"""IC/IR 计算引擎：使用 numpy 计算 Spearman 秩相关。"""

import numpy as np

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.evaluator import FactorExpressionEvaluator
from src.domain.strategy.factor_test.expressions import Expr


class ICCalculator:
    """因子 IC/IR 计算器。"""

    def __init__(self) -> None:
        self._evaluator = FactorExpressionEvaluator()

    def calculate_ic_series(
        self,
        expression: Expr,
        snapshots_by_date: dict[str, list[StockSnapshot]],
        returns_by_date: dict[str, dict[str, float]],
    ) -> list[tuple[str, float]]:
        """计算每个日期的 IC 值。

        Args:
            expression: 因子表达式 AST
            snapshots_by_date: {date_str: [StockSnapshot, ...]}
            returns_by_date: {date_str: {symbol: return_value}}

        Returns:
            [(date_str, ic_value), ...]
        """
        ic_series: list[tuple[str, float]] = []

        for date_str in sorted(snapshots_by_date.keys()):
            next_date = self._next_date(date_str, returns_by_date)
            if next_date is None:
                continue

            snapshots = snapshots_by_date[date_str]
            factor_values = self._evaluator.evaluate(expression, snapshots)
            next_returns = returns_by_date[next_date]

            ic = self._spearman_rank_correlation(factor_values, next_returns)
            ic_series.append((date_str, ic))

        return ic_series

    def calculate_ir(self, ic_series: list[float]) -> tuple[float, float, float]:
        """计算 IC 均值、标准差、IR。

        Returns:
            (ic_mean, ic_std, ir)
        """
        if not ic_series:
            return 0.0, 0.0, 0.0
        arr = np.array(ic_series)
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
        ir = mean / std if std > 0 else 0.0
        return mean, std, ir

    def _next_date(self, date_str: str, returns_by_date: dict[str, dict[str, float]]) -> str | None:
        """找到 date_str 之后的最近一个在 returns_by_date 中的日期。"""
        sorted_dates = sorted(returns_by_date.keys())
        for d in sorted_dates:
            if d > date_str:
                return d
        return None

    @staticmethod
    def _spearman_rank_correlation(
        x: dict[str, float], y: dict[str, float]
    ) -> float:
        """计算两个截面数据的 Spearman 秩相关系数。"""
        common = sorted(set(x) & set(y))
        if len(common) < 3:
            return 0.0

        x_vals = np.array([x[s] for s in common])
        y_vals = np.array([y[s] for s in common])

        # 排名
        x_rank = _rankdata(x_vals)
        y_rank = _rankdata(y_vals)

        # Pearson 相关 on ranks
        x_mean = np.mean(x_rank)
        y_mean = np.mean(y_rank)
        cov = np.sum((x_rank - x_mean) * (y_rank - y_mean))
        x_std = np.sqrt(np.sum((x_rank - x_mean) ** 2))
        y_std = np.sqrt(np.sum((y_rank - y_mean) ** 2))

        if x_std == 0 or y_std == 0:
            return 0.0
        return float(cov / (x_std * y_std))


def _rankdata(arr: np.ndarray) -> np.ndarray:
    """计算排名（平均排名法处理并列）。"""
    n = len(arr)
    ranked = np.empty(n)
    sorted_indices = np.argsort(arr)
    rank = 1
    i = 0
    while i < n:
        j = i
        while j < n - 1 and arr[sorted_indices[j + 1]] == arr[sorted_indices[j]]:
            j += 1
        avg_rank = (rank + rank + (j - i)) / 2.0
        for k in range(i, j + 1):
            ranked[sorted_indices[k]] = avg_rank
        rank += (j - i + 1)
        i = j + 1
    return ranked
