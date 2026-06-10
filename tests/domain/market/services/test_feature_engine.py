"""FeatureEngine golden 等价测试 — 向量化实现 vs 手写 CrossSectionBuilder。

参考实现 = 复刻 prepare_snapshots 旧循环（120 根窗口截断 + info_bars=recent[:-1]
+ CrossSectionBuilder._compute_bar_metrics）。逐日逐特征对比：

- 固定窗口特征: |diff| < 1e-9（含 缺失 ↔ NaN 一一对应）
- macd / macd_signal: 设计 §6 声明为**有意不同**的算法（全历史标准 EMA vs
  手写 120 窗重启近似），不与手写版比数值，只比缺失性对齐；数值正确性由
  独立的纯 Python 标准 EMA 递推参考实现钉死（1e-9）
- return_20d: 按修复口径单独断言（closes[-21]），不与手写 bug 口径比
"""

import math
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.domain.market.services.feature_engine import (
    FEATURE_COLUMNS,
    TECHNICAL_COLUMNS,
    compute_features,
    compute_symbol_features,
)
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.services.cross_section_builder import CrossSectionBuilder

_STRICT_TOL = 1e-9
_EMA_FEATURES = {"macd", "macd_signal"}  # 算法有意不同，只对比缺失性
_FIXED_SEMANTICS = {"return_20d"}  # 修复口径，不与手写版对比


def _make_random_bars(symbol: str, n: int, seed: int) -> list[Bar]:
    rng = random.Random(seed)
    bars: list[Bar] = []
    close = 10.0
    d0 = datetime(2023, 1, 2)
    for i in range(n):
        prev = close
        close = max(0.5, close * (1 + rng.gauss(0, 0.02)))
        opn = prev * (1 + rng.gauss(0, 0.005))
        high = max(opn, close) * (1 + abs(rng.gauss(0, 0.004)))
        low = min(opn, close) * (1 - abs(rng.gauss(0, 0.004)))
        bars.append(Bar(
            symbol=symbol,
            timeframe=Timeframe.DAY_1,
            timestamp=d0 + timedelta(days=i),
            open=opn, high=high, low=low, close=close,
            volume=rng.uniform(1e5, 5e6),
            prev_close=prev,
        ))
    return bars


def _bars_to_df(bars: list[Bar]) -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": [b.symbol for b in bars],
        "date": [b.timestamp for b in bars],
        "open": [b.open for b in bars],
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "close": [b.close for b in bars],
        "volume": [b.volume for b in bars],
        "prev_close": [b.prev_close for b in bars],
    })


def _reference_rows(bars: list[Bar]) -> dict[int, dict]:
    """复刻旧管道循环: 每个快照日 i 的手写特征 dict（120 根窗口截断）。"""
    rows: dict[int, dict] = {}
    for i in range(len(bars)):
        recent = bars[max(0, i - 119): i + 1]  # get_recent_bars(…, 120)
        if len(recent) < 2:
            continue
        info_bars = recent[:-1]
        kw: dict = {}
        CrossSectionBuilder._compute_bar_metrics(info_bars, kw)
        rows[i] = kw
    return rows


def _assert_feature_equal(name: str, hand, engine, day: int) -> None:
    hand_missing = hand is None
    engine_missing = engine is None or (isinstance(engine, float) and math.isnan(engine))
    assert hand_missing == engine_missing, (
        f"day={day} {name}: 缺失性不一致 hand={hand} engine={engine}"
    )
    if hand_missing or name in _EMA_FEATURES:
        return
    # 混合容差: 大数量级特征(如 OBV 斜率, 中间量 1e8 级)按相对 1e-9 —
    # 不同求和顺序的浮点舍入差, 语义仍为严格等价
    tol = max(_STRICT_TOL, _STRICT_TOL * abs(hand))
    assert abs(engine - hand) < tol, (
        f"day={day} {name}: hand={hand} engine={engine}"
    )


class TestGoldenEquivalence:
    def test_matches_handwritten_builder_per_day(self):
        bars = _make_random_bars("000001.SZ", 150, seed=42)
        reference = _reference_rows(bars)

        out = compute_symbol_features(_bars_to_df(bars))
        out_by_day = {ts: row for ts, row in zip(
            [b.timestamp for b in bars[1:]], out.to_dict("records"), strict=True
        )}

        for i, hand_kw in reference.items():
            row = out_by_day[bars[i].timestamp]
            for name in TECHNICAL_COLUMNS:
                if name in _FIXED_SEMANTICS:
                    continue
                _assert_feature_equal(name, hand_kw.get(name), row.get(name), day=i)

    def test_info_bar_and_exec_close_alignment(self):
        """行 = 快照日 T: info 列来自 T-1 bar, exec_close = T 日 close。"""
        bars = _make_random_bars("000001.SZ", 30, seed=7)
        out = compute_symbol_features(_bars_to_df(bars))

        assert len(out) == 29  # 首根 bar 无 T-1 信息
        for j, row in out.iterrows():
            i = j + 1  # 快照日在原始序列中的下标
            assert row["date"] == bars[i].timestamp
            assert abs(row["close"] - bars[i - 1].close) < _STRICT_TOL
            assert abs(row["volume"] - bars[i - 1].volume) < _STRICT_TOL
            assert abs(row["exec_close"] - bars[i].close) < _STRICT_TOL

    def test_return_20d_fixed_semantics(self):
        """修复口径: return_20d = (close[T-1] - close[T-21]) / close[T-21]。"""
        bars = _make_random_bars("000001.SZ", 150, seed=11)
        closes = [b.close for b in bars]
        out = compute_symbol_features(_bars_to_df(bars))

        for j, row in out.iterrows():
            i = j + 1
            if i - 1 >= 20:
                expected = (closes[i - 1] - closes[i - 21]) / closes[i - 21]
                assert abs(row["return_20d"] - expected) < _STRICT_TOL, f"day={i}"
            else:
                assert math.isnan(row["return_20d"])

    def test_macd_standard_ema_recursion(self):
        """macd 系按标准全历史 EMA 递推（首值为 seed, adjust=False 语义）。"""
        bars = _make_random_bars("000001.SZ", 150, seed=23)
        closes = [b.close for b in bars]
        out = compute_symbol_features(_bars_to_df(bars))

        def ema_series(values: list[float], span: int) -> list[float]:
            alpha = 2 / (span + 1)
            result = [values[0]]
            for x in values[1:]:
                result.append(x * alpha + result[-1] * (1 - alpha))
            return result

        e12 = ema_series(closes, 12)
        e26 = ema_series(closes, 26)
        macd_line = [a - b for a, b in zip(e12, e26, strict=True)]
        signal = ema_series(macd_line, 9)

        for j, row in out.iterrows():
            i = j + 1  # 快照日下标; macd 来自 T-1 = i-1
            if i - 1 >= 34:
                assert abs(row["macd"] - macd_line[i - 1]) < _STRICT_TOL, f"day={i}"
                assert abs(row["macd_signal"] - signal[i - 1]) < _STRICT_TOL, f"day={i}"
            else:
                assert math.isnan(row["macd"])
                assert math.isnan(row["macd_signal"])

    def test_multi_symbol_long_format(self):
        bars_a = _make_random_bars("000001.SZ", 80, seed=1)
        bars_b = _make_random_bars("600000.SH", 80, seed=2)
        long_df = pd.concat([_bars_to_df(bars_a), _bars_to_df(bars_b)], ignore_index=True)

        out = compute_features(long_df)

        assert list(out.columns) == list(FEATURE_COLUMNS)
        assert set(out["symbol"]) == {"000001.SZ", "600000.SH"}
        only_a = compute_symbol_features(_bars_to_df(bars_a))
        merged_a = out[out["symbol"] == "000001.SZ"].reset_index(drop=True)
        pd.testing.assert_frame_equal(merged_a, only_a)

    def test_short_history_returns_empty(self):
        bars = _make_random_bars("000001.SZ", 1, seed=3)
        out = compute_symbol_features(_bars_to_df(bars))
        assert out.empty
        assert list(out.columns) == list(FEATURE_COLUMNS)

    def test_nan_to_none_roundtrip_safety(self):
        """窗口不足处为 NaN（np.isnan 可判），供组装层转 None。"""
        bars = _make_random_bars("000001.SZ", 10, seed=5)
        out = compute_symbol_features(_bars_to_df(bars))
        first = out.iloc[0]
        assert np.isnan(first["return_60d"])
        assert np.isnan(first["volatility_20d"])
