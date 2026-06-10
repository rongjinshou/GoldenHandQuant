"""因子中性化(正交化): 横截面剥离 log市值 + return_20d 后重算残差 IC。

用于 §7.5 门槛: 若因子中性化后 IC 崩塌, 说明它只是市值/反转的影子。
"""

import math

import numpy as np

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.evaluator import FactorExpressionEvaluator
from src.domain.strategy.factor_test.lexer import tokenize
from src.domain.strategy.factor_test.parser import FactorExpressionParser
from src.infrastructure.factor_test.ic_calculator import ICCalculator


class FactorNeutralizer:
    """对因子做横截面中性化, 再算残差对下期收益的 IC。"""

    def __init__(self) -> None:
        self._parser = FactorExpressionParser()
        self._evaluator = FactorExpressionEvaluator()

    def mean_neutralized_ic(
        self,
        expression_str: str,
        snapshots_by_date: dict[str, list[StockSnapshot]],
        returns_by_date: dict[str, dict[str, float]],
    ) -> float:
        """剥离市值/反转后的平均 IC。控制变量缺失或残差退化的日期跳过。"""
        expr = self._parser.parse(tokenize(expression_str))
        ics: list[float] = []
        for date_str in sorted(snapshots_by_date.keys()):
            next_date = self._next_date(date_str, returns_by_date)
            if next_date is None:
                continue
            factor_values = self._evaluator.evaluate(expr, snapshots_by_date[date_str])
            residuals = self._residualize(factor_values, snapshots_by_date[date_str])
            if not residuals:
                continue
            ic = ICCalculator._spearman_rank_correlation(residuals, returns_by_date[next_date])
            ics.append(ic)
        if not ics:
            return 0.0
        return float(sum(ics) / len(ics))

    @staticmethod
    def _residualize(
        factor_values: dict[str, float],
        snapshots: list[StockSnapshot],
    ) -> dict[str, float]:
        """对 [1, log(market_cap), return_20d] 横截面回归, 返回 {sym: 残差}。"""
        rows: list[tuple[str, float, float, float]] = []
        for s in snapshots:
            if s.symbol not in factor_values:
                continue
            mc = getattr(s, "market_cap", None)
            r20 = getattr(s, "return_20d", None)
            if mc is None or mc <= 0 or r20 is None:
                continue
            rows.append((s.symbol, factor_values[s.symbol], math.log(mc), float(r20)))
        if len(rows) < 3:
            return {}

        y = np.array([r[1] for r in rows], dtype=float)
        y_scale = float(np.std(y))
        if y_scale < 1e-12:           # 因子本身近似常数, 无信号
            return {}

        x = np.array([[1.0, r[2], r[3]] for r in rows], dtype=float)
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        resid = y - x @ coef
        if float(np.std(resid)) < 1e-7 * y_scale:   # 残差退化(因子≈控制变量线性组合)
            return {}
        return {rows[i][0]: float(resid[i]) for i in range(len(rows))}

    @staticmethod
    def _next_date(date_str: str, returns_by_date: dict[str, dict[str, float]]) -> str | None:
        for d in sorted(returns_by_date.keys()):
            if d > date_str:
                return d
        return None
