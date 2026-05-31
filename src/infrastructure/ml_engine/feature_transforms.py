"""衍生特征计算与截面标准化。"""

from __future__ import annotations

import math

import pandas as pd

from src.domain.market.value_objects.stock_snapshot import StockSnapshot

# StockSnapshot 上可用于提取的基础特征字段
_SNAPSHOT_FEATURE_FIELDS: list[str] = [
    "return_5d", "return_20d", "return_60d",
    "volatility_20d", "volatility_60d",
    "turnover_rate", "avg_turnover_20d",
    "rsi_14", "macd", "macd_signal",
    "ma_5", "ma_20", "ma_60",
    "high_20d", "low_20d",
    "atr_14", "skewness_20d", "illiquidity_20d", "obv_slope_20d",
    "pe_ratio", "pb_ratio",
    "roe_ttm",
    "market_cap",
]


def extract_base_features(snapshot: StockSnapshot) -> dict[str, float | None]:
    """从 StockSnapshot 提取基础特征字典。"""
    features: dict[str, float | None] = {}
    for field in _SNAPSHOT_FEATURE_FIELDS:
        features[field] = getattr(snapshot, field, None)
    features["symbol"] = snapshot.symbol  # type: ignore[assignment]
    features["date"] = snapshot.date  # type: ignore[assignment]
    return features


def compute_derived_features(rows: list[dict[str, float | None]]) -> list[dict[str, float | None]]:
    """在基础特征之上计算衍生特征。

    Args:
        rows: 每个元素是 extract_base_features 返回的字典。

    Returns:
        原地追加衍生特征后的 rows（同时返回方便链式调用）。
    """
    for row in rows:
        close = _safe_get(row, "close") or _derive_close(row)
        ma_5 = row.get("ma_5")
        ma_20 = row.get("ma_20")
        ma_60 = row.get("ma_60")
        high_20d = row.get("high_20d")
        low_20d = row.get("low_20d")
        macd = row.get("macd")
        macd_signal = row.get("macd_signal")
        pb_ratio = row.get("pb_ratio")
        market_cap = row.get("market_cap")
        turnover_rate = row.get("turnover_rate")
        avg_turnover_20d = row.get("avg_turnover_20d")

        # 均线偏离度
        row["close_to_ma5"] = _ratio(close, ma_5)
        row["close_to_ma20"] = _ratio(close, ma_20)
        row["close_to_ma60"] = _ratio(close, ma_60)

        # 均线交叉
        row["ma5_to_ma20"] = _ratio(ma_5, ma_20)
        row["ma20_to_ma60"] = _ratio(ma_20, ma_60)

        # 价格区间
        if high_20d is not None and low_20d is not None and close and close > 0:
            row["high_low_range"] = (high_20d - low_20d) / close
            denom = high_20d - low_20d
            row["close_position"] = (close - low_20d) / denom if denom > 0 else None
        else:
            row["high_low_range"] = None
            row["close_position"] = None

        # MACD 柱
        if macd is not None and macd_signal is not None:
            row["macd_hist"] = macd - macd_signal
        else:
            row["macd_hist"] = None

        # 对数市值
        if market_cap is not None and market_cap > 0:
            row["log_market_cap"] = math.log(market_cap)
        else:
            row["log_market_cap"] = None

        # 账面市值比
        if pb_ratio is not None and pb_ratio > 0:
            row["bp_ratio"] = 1.0 / pb_ratio
        else:
            row["bp_ratio"] = None

        # 波动变化率 (5d vs 20d)
        row["vol_ratio_5_20"] = None  # 需要 5d 波动率，当前数据不可用时留空

        # 异常换手率 z-score
        if turnover_rate is not None and avg_turnover_20d is not None and avg_turnover_20d > 0:
            row["turnover_zscore"] = (turnover_rate - avg_turnover_20d) / avg_turnover_20d
        else:
            row["turnover_zscore"] = None

    return rows


def cross_section_standardize(
    df: pd.DataFrame,
    feature_cols: list[str],
    date_col: str = "date",
) -> pd.DataFrame:
    """每日截面内 Z-Score 标准化。

    对每个日期组，将 feature_cols 标准化为均值 0、标准差 1。
    原地修改并返回。
    """
    for _date, group in df.groupby(date_col):
        for col in feature_cols:
            vals = group[col]
            mean = vals.mean()
            std = vals.std()
            if std > 0:
                df.loc[group.index, col] = (vals - mean) / std
            else:
                df.loc[group.index, col] = 0.0
    return df


# -- 私有辅助函数 --

def _safe_get(row: dict, key: str) -> float | None:
    v = row.get(key)
    return v if v is not None else None


def _derive_close(row: dict) -> float | None:
    """从 ma_5 或其他指标反推 close（近似），通常 StockSnapshot 已有 close。"""
    return None


def _ratio(a: float | None, b: float | None) -> float | None:
    if a is not None and b is not None and b > 0:
        return a / b - 1.0
    return None
