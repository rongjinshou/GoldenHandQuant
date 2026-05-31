"""模型评估器：IC 分析 + 分层回测。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


@dataclass(slots=True, kw_only=True)
class PredictionMetrics:
    """预测评估指标。"""
    ic: float
    ic_ir: float
    ic_positive_ratio: float
    rank_autocorrelation: float


@dataclass(slots=True, kw_only=True)
class QuintileResult:
    """分层回测结果。"""
    quintile: int
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    turnover: float


@dataclass(slots=True, kw_only=True)
class EvalReport:
    """完整评估报告。"""
    model_name: str
    eval_period: str
    prediction_metrics: PredictionMetrics
    quintile_results: list[QuintileResult]
    long_short_return: float
    feature_importance: dict[str, float]


class ModelEvaluator:
    """模型评估器。"""

    def evaluate_predictions(
        self,
        predictions: pd.DataFrame,
    ) -> PredictionMetrics:
        """评估预测质量（按日截面 IC）。

        Args:
            predictions: columns=[date, symbol, pred, actual]。
        """
        ics: list[float] = []
        for _date, group in predictions.groupby("date"):
            if len(group) < 5:
                continue
            ic, _ = spearmanr(group["pred"], group["actual"])
            if not np.isnan(ic):
                ics.append(ic)

        if not ics:
            return PredictionMetrics(ic=0.0, ic_ir=0.0, ic_positive_ratio=0.0, rank_autocorrelation=0.0)

        mean_ic = float(np.mean(ics))
        ic_std = float(np.std(ics))
        ic_ir = mean_ic / ic_std if ic_std > 0 else 0.0
        ic_positive = float(np.mean([1.0 for ic in ics if ic > 0]))

        # IC 自相关（lag-1）
        if len(ics) > 1:
            autocorr = float(np.corrcoef(ics[:-1], ics[1:])[0, 1])
            if np.isnan(autocorr):
                autocorr = 0.0
        else:
            autocorr = 0.0

        return PredictionMetrics(
            ic=mean_ic,
            ic_ir=ic_ir,
            ic_positive_ratio=ic_positive,
            rank_autocorrelation=autocorr,
        )

    def evaluate_quintiles(
        self,
        predictions: pd.DataFrame,
        price_data: dict[str, pd.Series],
        n_quintiles: int = 5,
    ) -> list[QuintileResult]:
        """分层回测评估。"""
        # 每日按预测分数分组
        daily_returns: dict[int, list[float]] = {q: [] for q in range(1, n_quintiles + 1)}

        for _date, group in predictions.groupby("date"):
            if len(group) < n_quintiles:
                continue
            group = group.copy()
            group["quintile"] = pd.qcut(group["pred"].rank(method="first"), n_quintiles, labels=False) + 1

            for q in range(1, n_quintiles + 1):
                q_group = group[group["quintile"] == q]
                if q_group.empty:
                    continue
                # 使用 actual_return 作为收益
                avg_ret = q_group["actual"].mean()
                daily_returns[q].append(avg_ret)

        results: list[QuintileResult] = []
        for q in range(1, n_quintiles + 1):
            rets = daily_returns[q]
            if not rets:
                results.append(QuintileResult(
                    quintile=q, annualized_return=0.0, sharpe_ratio=0.0,
                    max_drawdown=0.0, turnover=0.0,
                ))
                continue

            rets_arr = np.array(rets)
            ann_ret = float(np.mean(rets_arr) * 252)
            std = float(np.std(rets_arr))
            sharpe = float(np.mean(rets_arr) / std * np.sqrt(252)) if std > 0 else 0.0

            # 最大回撤
            cum = np.cumprod(1 + rets_arr)
            running_max = np.maximum.accumulate(cum)
            dd = (cum - running_max) / running_max
            max_dd = float(np.min(dd)) if len(dd) > 0 else 0.0

            results.append(QuintileResult(
                quintile=q, annualized_return=ann_ret, sharpe_ratio=sharpe,
                max_drawdown=max_dd, turnover=0.0,
            ))

        return results

    def full_evaluation(
        self,
        model_name: str,
        predictions: pd.DataFrame,
        price_data: dict[str, pd.Series],
        feature_importance: dict[str, float] | None = None,
    ) -> EvalReport:
        """完整评估报告。"""
        pred_metrics = self.evaluate_predictions(predictions)
        quintile_results = self.evaluate_quintiles(predictions, price_data)

        # 多空收益
        if len(quintile_results) >= 2:
            long_short = quintile_results[-1].annualized_return - quintile_results[0].annualized_return
        else:
            long_short = 0.0

        dates = predictions["date"].unique()
        eval_period = f"{min(dates)} ~ {max(dates)}" if len(dates) > 0 else ""

        return EvalReport(
            model_name=model_name,
            eval_period=eval_period,
            prediction_metrics=pred_metrics,
            quintile_results=quintile_results,
            long_short_return=long_short,
            feature_importance=feature_importance or {},
        )
