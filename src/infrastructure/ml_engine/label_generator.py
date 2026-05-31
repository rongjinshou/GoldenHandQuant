"""标签生成器：计算前瞻收益并 Winsorize。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True, kw_only=True)
class LabelConfig:
    """标签生成配置。"""
    horizon: int = 20
    label_type: str = "fwd_return"  # "fwd_return" | "fwd_excess"
    winsorize_quantile: float = 0.01


def generate_labels(
    df: pd.DataFrame,
    price_series: dict[str, pd.Series],
    config: LabelConfig,
) -> pd.Series:
    """为数据集生成前瞻收益标签。

    Args:
        df: 包含 date, symbol 列的数据集。
        price_series: {symbol: Series(index=date, values=close)}。
        config: 标签配置。

    Returns:
        与 df 等长的 Series，含 NaN（停牌/数据不足）。
    """
    labels = pd.Series(np.nan, index=df.index, name="label")

    for symbol, prices in price_series.items():
        mask = df["symbol"] == symbol
        if not mask.any():
            continue

        sub = df.loc[mask].sort_values("date")
        dates = sub["date"].values

        # 构建日期到价格的映射
        price_map = prices.to_dict()

        label_vals: list[float] = []
        for dt in dates:
            current_price = price_map.get(dt)
            if current_price is None or current_price <= 0:
                label_vals.append(np.nan)
                continue

            # 找到 t + horizon 个交易日后的价格
            target_date = _shift_date(dates, dt, config.horizon)
            if target_date is None:
                label_vals.append(np.nan)
                continue

            future_price = price_map.get(target_date)
            if future_price is None or future_price <= 0:
                label_vals.append(np.nan)
                continue

            label_vals.append(future_price / current_price - 1.0)

        labels.loc[mask] = label_vals

    # Winsorize
    q = config.winsorize_quantile
    if 0 < q < 0.5:
        lower = labels.quantile(q)
        upper = labels.quantile(1 - q)
        labels = labels.clip(lower=lower, upper=upper)

    return labels


def _shift_date(sorted_dates: np.ndarray, current: np.datetime64, n: int) -> np.datetime64 | None:
    """在有序日期数组中找到 current 之后第 n 个交易日。"""
    idx = np.searchsorted(sorted_dates, current)
    target_idx = idx + n
    if target_idx < len(sorted_dates):
        return sorted_dates[target_idx]
    return None
