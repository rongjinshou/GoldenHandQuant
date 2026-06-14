"""向量化因子中性化 — 横截面剥离 [1, log(market_cap), return_20d] 后残差 IC。

与对象式 ``FactorNeutralizer.mean_neutralized_ic`` 逐位等价(设计 §6): 每日 OLS 残差
按 df 行序输入 lstsq(顺序无关于结果但保浮点一致), 退化守门(y 近常数 / 残差退化)同口径;
残差 IC 复用 ``ICCalculator._spearman_rank_correlation`` 保证 spearman 一致。
"""

import bisect

import numpy as np
import pandas as pd

from src.domain.strategy.factor_test.lexer import tokenize
from src.domain.strategy.factor_test.panel import FactorPanel
from src.domain.strategy.factor_test.parser import FactorExpressionParser
from src.domain.strategy.factor_test.vectorized_evaluator import VectorizedEvaluator
from src.infrastructure.factor_test.ic_calculator import ICCalculator


class VectorizedNeutralizer:
    """列式因子中性化。"""

    def __init__(self) -> None:
        self._parser = FactorExpressionParser()
        self._evaluator = VectorizedEvaluator()

    def mean_neutralized_ic(self, expression_str: str, panel: FactorPanel) -> float:
        """剥离市值/反转后的平均 IC。控制变量缺失或残差退化的日期跳过。"""
        expr = self._parser.parse(tokenize(expression_str))
        df = panel.df
        if df.empty:
            return 0.0
        factor_series = self._evaluator.evaluate(expr, df)

        work = pd.DataFrame({
            "date_str": pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d").to_numpy(),
            "symbol": df["symbol"].to_numpy(),
            "factor": factor_series.to_numpy(),
            "mc": pd.to_numeric(df.get("market_cap"), errors="coerce").to_numpy()
            if "market_cap" in df.columns else np.nan,
            "r20": pd.to_numeric(df.get("return_20d"), errors="coerce").to_numpy()
            if "return_20d" in df.columns else np.nan,
        }).dropna(subset=["factor"])
        work = work[work["mc"] > 0].dropna(subset=["r20"])
        if work.empty:
            return 0.0
        work["log_mc"] = np.log(work["mc"].to_numpy())

        residuals_by_date: dict[str, dict[str, float]] = {}
        for date_str, sub in work.groupby("date_str", sort=True):
            resid = self._residualize(sub)
            if resid:
                residuals_by_date[date_str] = resid

        returns_by_date = panel.forward_returns()
        ret_keys = sorted(returns_by_date.keys())

        ics: list[float] = []
        for date_str in sorted(residuals_by_date.keys()):
            j = bisect.bisect_right(ret_keys, date_str)
            if j >= len(ret_keys):
                continue
            ic = ICCalculator._spearman_rank_correlation(
                residuals_by_date[date_str], returns_by_date[ret_keys[j]]
            )
            ics.append(ic)
        if not ics:
            return 0.0
        return float(sum(ics) / len(ics))

    @staticmethod
    def _residualize(sub: pd.DataFrame) -> dict[str, float]:
        """对 [1, log(market_cap), return_20d] 横截面回归, 返回 {sym: 残差}(退化→空)。"""
        if len(sub) < 3:
            return {}
        y = sub["factor"].to_numpy(dtype=float)
        y_scale = float(np.std(y))
        if y_scale < 1e-12:
            return {}
        x = np.column_stack([
            np.ones(len(sub)), sub["log_mc"].to_numpy(dtype=float),
            sub["r20"].to_numpy(dtype=float),
        ])
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        resid = y - x @ coef
        if float(np.std(resid)) < 1e-7 * y_scale:
            return {}
        return dict(zip(sub["symbol"], (float(v) for v in resid), strict=True))
