"""因子有效性评估器 — IC/IR/分层回测/衰减分析。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


@dataclass(slots=True, kw_only=True)
class FactorEvalResult:
    """因子评估结果。"""
    factor_name: str
    ic_mean: float
    ic_std: float
    ir: float
    ic_positive_ratio: float
    monotonicity: float
    sharpe_by_group: list[float]
    annual_return_by_group: list[float]
    ic_decay: dict[int, float]
    is_effective: bool


class FactorEvaluator:
    """因子有效性评估器。"""

    IC_THRESHOLD = 0.03
    IR_THRESHOLD = 0.5
    IC_POSITIVE_THRESHOLD = 0.55
    SHARPE_THRESHOLD = 1.0
    MONOTONICITY_THRESHOLD = 0.8

    def compute_ic_series(
        self,
        factor_values: pd.DataFrame,
        forward_returns: pd.DataFrame,
    ) -> pd.Series:
        """计算每期截面 IC 时间序列。

        Args:
            factor_values: index=date, columns=symbol
            forward_returns: index=date, columns=symbol

        Returns:
            Series, index=date, values=Spearman rank correlation。
        """
        common_dates = factor_values.index.intersection(forward_returns.index)
        common_symbols = factor_values.columns.intersection(forward_returns.columns)

        ic_values: list[float] = []
        ic_dates: list = []

        for dt in common_dates:
            fv = factor_values.loc[dt, common_symbols]
            fr = forward_returns.loc[dt, common_symbols]

            # 丢弃 NaN 对
            mask = fv.notna() & fr.notna()
            fv_clean = fv[mask]
            fr_clean = fr[mask]

            if len(fv_clean) < 30:
                continue

            corr, _ = spearmanr(fv_clean.values, fr_clean.values)
            if np.isnan(corr):
                continue

            ic_values.append(corr)
            ic_dates.append(dt)

        return pd.Series(ic_values, index=ic_dates, name="IC")

    def evaluate_single(
        self,
        factor_values: pd.DataFrame,
        forward_returns: pd.DataFrame,
        factor_name: str = "",
        forward_days_list: list[int] | None = None,
    ) -> FactorEvalResult:
        """评估单个因子的有效性。"""
        if forward_days_list is None:
            forward_days_list = [20]

        ic_series = self.compute_ic_series(factor_values, forward_returns)

        if len(ic_series) == 0:
            return FactorEvalResult(
                factor_name=factor_name,
                ic_mean=0.0, ic_std=0.0, ir=0.0,
                ic_positive_ratio=0.0, monotonicity=0.0,
                sharpe_by_group=[0.0] * 5, annual_return_by_group=[0.0] * 5,
                ic_decay={}, is_effective=False,
            )

        ic_mean = float(ic_series.mean())
        ic_std = float(ic_series.std())
        ir = ic_mean / ic_std if ic_std > 1e-10 else 0.0
        ic_positive_ratio = float((ic_series > 0).mean())

        # 分层回测
        group_returns = self._compute_quintile_returns(
            factor_values, forward_returns
        )
        sharpe_by_group = self._compute_sharpe_by_group(group_returns)
        annual_return_by_group = self._compute_annual_return_by_group(group_returns)
        monotonicity = self._compute_monotonicity(group_returns)

        # IC 衰减（简化：仅用单期 IC 作为 baseline）
        ic_decay: dict[int, float] = {}
        for fwd in forward_days_list:
            if fwd == 20:
                ic_decay[fwd] = ic_mean

        is_effective = self._check_effective(ic_mean, ir, ic_positive_ratio)

        return FactorEvalResult(
            factor_name=factor_name,
            ic_mean=ic_mean,
            ic_std=ic_std,
            ir=ir,
            ic_positive_ratio=ic_positive_ratio,
            monotonicity=monotonicity,
            sharpe_by_group=sharpe_by_group,
            annual_return_by_group=annual_return_by_group,
            ic_decay=ic_decay,
            is_effective=is_effective,
        )

    def evaluate_batch(
        self,
        factor_dict: dict[str, pd.DataFrame],
        forward_returns: pd.DataFrame,
        top_n: int = 20,
    ) -> list[FactorEvalResult]:
        """批量评估，返回按 |IR| 排序的 top_n。"""
        results: list[FactorEvalResult] = []

        for name, fv in factor_dict.items():
            result = self.evaluate_single(fv, forward_returns, factor_name=name)
            results.append(result)

        results.sort(key=lambda r: abs(r.ir), reverse=True)
        return results[:top_n]

    def compute_ic_decay(
        self,
        factor_values: pd.DataFrame,
        returns_by_horizon: dict[int, pd.DataFrame],
    ) -> dict[int, float]:
        """计算不同前瞻期的平均 IC。"""
        decay: dict[int, float] = {}
        for horizon, fwd_ret in returns_by_horizon.items():
            ic_series = self.compute_ic_series(factor_values, fwd_ret)
            decay[horizon] = float(ic_series.mean()) if len(ic_series) > 0 else 0.0
        return decay

    def _compute_quintile_returns(
        self,
        factor_values: pd.DataFrame,
        forward_returns: pd.DataFrame,
        n_groups: int = 5,
    ) -> pd.DataFrame:
        """按因子值分 N 组，计算每组的平均前瞻收益。"""
        common_dates = factor_values.index.intersection(forward_returns.index)
        common_symbols = factor_values.columns.intersection(forward_returns.columns)

        group_data: dict[str, list[float]] = {
            f"group_{i}": [] for i in range(n_groups)
        }

        for dt in common_dates:
            fv = factor_values.loc[dt, common_symbols]
            fr = forward_returns.loc[dt, common_symbols]

            mask = fv.notna() & fr.notna()
            fv_clean = fv[mask]
            fr_clean = fr[mask]

            if len(fv_clean) < n_groups * 5:
                continue

            # 按因子值分组
            try:
                groups = pd.qcut(fv_clean, n_groups, labels=False, duplicates="drop")
            except ValueError:
                continue

            for g in range(n_groups):
                g_mask = groups == g
                if g_mask.any():
                    group_data[f"group_{g}"].append(float(fr_clean[g_mask].mean()))

        return pd.DataFrame(group_data)

    @staticmethod
    def _compute_monotonicity(group_returns: pd.DataFrame) -> float:
        """计算分层单调性评分 (0-1)。

        单调性 = 相邻组收益单调递增的比例。
        """
        if group_returns.empty or len(group_returns.columns) < 2:
            return 0.0

        monotone_count = 0
        total = 0

        for _, row in group_returns.iterrows():
            vals = row.values
            valid = ~np.isnan(vals)
            if valid.sum() < 2:
                continue

            valid_vals = vals[valid]
            increasing = all(
                valid_vals[i] <= valid_vals[i + 1]
                for i in range(len(valid_vals) - 1)
            )
            decreasing = all(
                valid_vals[i] >= valid_vals[i + 1]
                for i in range(len(valid_vals) - 1)
            )
            if increasing or decreasing:
                monotone_count += 1
            total += 1

        return monotone_count / total if total > 0 else 0.0

    @staticmethod
    def _compute_sharpe_by_group(group_returns: pd.DataFrame) -> list[float]:
        """计算每组的年化夏普比率。"""
        sharpes: list[float] = []
        for col in group_returns.columns:
            vals = group_returns[col].dropna()
            if len(vals) < 2:
                sharpes.append(0.0)
                continue
            mean = vals.mean()
            std = vals.std()
            # 假设每期是日频，年化因子 sqrt(252)
            sharpe = (mean / std * np.sqrt(252)) if std > 1e-10 else 0.0
            sharpes.append(float(sharpe))
        return sharpes

    @staticmethod
    def _compute_annual_return_by_group(group_returns: pd.DataFrame) -> list[float]:
        """计算每组的年化收益率。"""
        annual_returns: list[float] = []
        for col in group_returns.columns:
            vals = group_returns[col].dropna()
            if len(vals) == 0:
                annual_returns.append(0.0)
                continue
            # 累积收益
            cum = (1 + vals).prod()
            n_periods = len(vals)
            if n_periods > 0 and cum > 0:
                annual = cum ** (252 / max(n_periods, 1)) - 1
            else:
                annual = 0.0
            annual_returns.append(float(annual))
        return annual_returns

    def _check_effective(
        self,
        ic_mean: float,
        ir: float,
        ic_positive_ratio: float,
    ) -> bool:
        """检查因子是否通过有效性筛选。"""
        return (
            abs(ic_mean) > self.IC_THRESHOLD
            and abs(ir) > self.IR_THRESHOLD
            and ic_positive_ratio > self.IC_POSITIVE_THRESHOLD
        )
