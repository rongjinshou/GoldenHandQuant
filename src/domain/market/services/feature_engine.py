"""向量化截面特征引擎 — 单 symbol 全时段一次计算（T-1 信息约定）。

替代 CrossSectionBuilder 的"每日 × 每股 × 120 根重算"路径。语义对齐手写版
（窗口长度、守卫条件、样本标准差 ddof=1、Cutler RSI、总体偏度），两点例外：

1. return_20d **修复**为 closes[-21] 口径（手写版误用 closes[0]，在 120 根
   窗口下实际是 ~119 日收益）— 该修复定义 FEATURE_VERSION=1。
2. macd / macd_signal 用标准全历史 EMA 递推（手写版为 120 根窗口内重启的
   近似，两者差异 ~1e-6 量级）。

设计文档: docs/feat/0611-market-data-store/2026-06-11-market-data-store-design.md §6
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_VERSION = 1  # return_20d 修复后的首版口径

# 取数提前量(自然日): 让窗口开头也能算出 return_60d / volatility 等需历史的特征
WARMUP_DAYS = 200

INFO_BAR_COLUMNS = ("open", "high", "low", "close", "volume", "prev_close")
TECHNICAL_COLUMNS = (
    "return_5d", "return_20d", "return_60d",
    "volatility_20d", "volatility_60d",
    "turnover_rate", "avg_turnover_20d",
    "rsi_14", "macd", "macd_signal",
    "ma_5", "ma_20", "ma_60",
    "high_20d", "low_20d", "atr_14",
    "skewness_20d", "illiquidity_20d", "obv_slope_20d",
)
# stock_features 表的列契约（infrastructure/application 共用）
FEATURE_COLUMNS = ("symbol", "date", *INFO_BAR_COLUMNS, "exec_close", *TECHNICAL_COLUMNS)


def compute_features(bars_df: pd.DataFrame) -> pd.DataFrame:
    """多 symbol 长表入口: 按 symbol 分组逐只向量化计算后拼接。"""
    if bars_df.empty:
        return pd.DataFrame(columns=list(FEATURE_COLUMNS))
    parts = [
        compute_symbol_features(g)
        for _, g in bars_df.groupby("symbol", sort=False)
    ]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame(columns=list(FEATURE_COLUMNS))
    return pd.concat(parts, ignore_index=True)


def compute_symbol_features(bars_df: pd.DataFrame) -> pd.DataFrame:
    """单 symbol 特征序列。

    Args:
        bars_df: 列含 symbol/date/open/high/low/close/volume/prev_close，
            date 升序、无重复（单 symbol）。

    Returns:
        FEATURE_COLUMNS 列的 DataFrame。行 = 快照日 T（自第 2 根 bar 起，
        对应旧管道 ``len(recent) < 2: continue``）；info bar 列与全部技术
        指标来自 T-1 及更早（先按 T-1 截止计算，再 shift 对齐到 T）；
        exec_close = T 日 close；窗口不足 → NaN。
    """
    if len(bars_df) < 2:
        return pd.DataFrame(columns=list(FEATURE_COLUMNS))

    df = bars_df.reset_index(drop=True)
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    lo = df["low"].astype(float)
    v = df["volume"].astype(float)
    n = len(df)
    idx = np.arange(n)

    ret1 = c.pct_change(fill_method=None)

    asof: dict[str, pd.Series] = {}

    # --- 收益率（return_20d 为修复口径 pct_change(20)） ---
    asof["return_5d"] = c.pct_change(5, fill_method=None)
    asof["return_20d"] = c.pct_change(20, fill_method=None)
    asof["return_60d"] = c.pct_change(60, fill_method=None)

    # --- 波动率（样本标准差 ddof=1，与手写 _std 一致） ---
    asof["volatility_20d"] = ret1.rolling(20).std(ddof=1)
    asof["volatility_60d"] = ret1.rolling(60).std(ddof=1)

    # --- 换手（20 日均量允许不足 20 根，对齐手写 min(20, n)） ---
    avg20 = v.rolling(20, min_periods=1).mean()
    turnover_valid = (v > 0) & (avg20 > 0)
    asof["turnover_rate"] = (v / avg20).where(turnover_valid)
    asof["avg_turnover_20d"] = avg20.where(turnover_valid)

    # --- RSI 14（Cutler: 近 14 日涨/跌幅简单平均；无跌幅 → 100） ---
    avg_gain = ret1.clip(lower=0).rolling(14).sum() / 14
    avg_loss = (-ret1.clip(upper=0)).rolling(14).sum() / 14
    rsi = pd.Series(np.where(avg_loss > 0, 100 - 100 / (1 + avg_gain / avg_loss), 100.0))
    asof["rsi_14"] = rsi.where(avg_gain.notna() & avg_loss.notna())

    # --- MACD（标准全历史 EMA 递推；可用性窗口对齐手写 n>=35） ---
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_mask = idx >= 34
    asof["macd"] = macd_line.where(macd_mask)
    asof["macd_signal"] = macd_signal.where(macd_mask)

    # --- 均线 / 20 日高低 ---
    asof["ma_5"] = c.rolling(5).mean()
    asof["ma_20"] = c.rolling(20).mean()
    asof["ma_60"] = c.rolling(60).mean()
    asof["high_20d"] = h.rolling(20).max()
    asof["low_20d"] = lo.rolling(20).min()

    # --- ATR 14 ---
    prev_c = c.shift(1)
    tr = pd.concat(
        [h - lo, (h - prev_c).abs(), (lo - prev_c).abs()], axis=1
    ).max(axis=1)
    tr[prev_c.isna()] = np.nan  # 首日无前收，不计 TR（对齐手写从第 2 根起）
    asof["atr_14"] = tr.rolling(14).mean()

    # --- 偏度 20 日（总体偏度 ÷n、样本 std；闭式展开避免逐窗 apply） ---
    m1 = ret1.rolling(20).mean()
    m2 = (ret1**2).rolling(20).mean()
    m3 = (ret1**3).rolling(20).mean()
    s = ret1.rolling(20).std(ddof=1)
    central3 = m3 - 3 * m1 * m2 + 2 * m1**3
    asof["skewness_20d"] = (central3 / s**3).where(s > 0)

    # --- Amihud 非流动性（窗口内仅统计 volume>0 的日子，对齐手写 skip 语义） ---
    illiq_daily = (ret1.abs() / v.where(v > 0)).where(ret1.notna())
    illiq = illiq_daily.rolling(20, min_periods=1).mean()
    asof["illiquidity_20d"] = illiq.where(idx >= 20)

    # --- OBV 20 点斜率（OBV 平移不变 → 全历史累计与窗口重启等价） ---
    obv = (np.sign(c.diff().fillna(0.0)) * v).cumsum()
    w = (np.arange(20) - 9.5) / 665.0  # Σ(i-9.5)² = 665
    slope = sum(obv.shift(19 - k) * w[k] for k in range(20))
    asof["obv_slope_20d"] = slope.where(idx >= 20)  # 手写守卫 n>=21

    out = pd.DataFrame({
        "symbol": df["symbol"],
        "date": df["date"],
        "exec_close": c,
    })
    for col in INFO_BAR_COLUMNS:
        out[col] = df[col].astype(float).shift(1)
    for name, series in asof.items():
        out[name] = series.shift(1)

    out = out.iloc[1:].reset_index(drop=True)  # 首根 bar 无 T-1 信息，不产快照
    return out[list(FEATURE_COLUMNS)]
