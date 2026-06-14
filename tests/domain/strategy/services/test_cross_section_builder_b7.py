"""B7: build_cross_section 的 precomputed_features 路径 + 纠错定点差异。"""

from datetime import datetime, timedelta

import pytest

from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.services.snapshot_feature_source import (
    FeatureEngineSnapshotSource,
)
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.services.cross_section_builder import CrossSectionBuilder


def _window(n: int) -> list[Bar]:
    base = datetime(2024, 1, 1)
    bars, prev = [], 0.0
    for i in range(n):
        c = 10.0 + i * 0.1 + (i % 5) * 0.3 - (i % 7) * 0.2
        bars.append(Bar(
            symbol="X", timeframe=Timeframe.DAY_1,
            timestamp=base + timedelta(days=i),
            open=c - 0.1, high=c + 0.25, low=c - 0.2, close=c,
            volume=1000.0 + (i % 9) * 50, prev_close=prev or c,
        ))
        prev = c
    return bars


def _registry(at: datetime) -> FundamentalRegistry:
    reg = FundamentalRegistry()
    reg.load_snapshots([FundamentalSnapshot(
        symbol="X", date=at, name="X股", list_date=datetime(2018, 1, 1),
        market_cap=1e10, pe_ratio=15.0, pb_ratio=2.0,
        earnings_growth=0.1, revenue_growth=0.2,
    )])
    return reg


def test_precomputed_features_used_and_skips_recompute():
    """给 precomputed_features 时快照技术字段取自它, 不调 _compute_bar_metrics。"""
    win = _window(80)
    snap_bar = {"X": win[-2]}  # T-1 bar
    reg = _registry(win[-1].timestamp)
    pre = {"X": {"return_20d": 0.4242, "rsi_14": 55.0}}

    snaps = CrossSectionBuilder.build_cross_section(
        win[-1].timestamp, snap_bar, reg, precomputed_features=pre,
    )
    assert len(snaps) == 1
    s = snaps[0]
    assert s.return_20d == pytest.approx(0.4242)
    assert s.rsi_14 == pytest.approx(55.0)
    # 未在 pre 中的技术字段保持缺失(说明没走手写重算)
    assert s.macd is None
    assert s.volatility_20d is None


def test_without_precomputed_uses_legacy_path():
    """不给 precomputed_features 时维持旧 bar_history 路径(回归)。"""
    win = _window(80)
    snap_bar = {"X": win[-2]}
    reg = _registry(win[-1].timestamp)
    snaps = CrossSectionBuilder.build_cross_section(
        win[-1].timestamp, snap_bar, reg, bar_history={"X": win[:-1]},
    )
    s = snaps[0]
    assert s.return_20d is not None      # 旧 _compute_bar_metrics 路径
    assert s.volatility_20d is not None


def test_b7_targeted_diff_return20d_fixed_rest_aligned():
    """新(feature_engine)vs 旧(_compute_bar_metrics): return_20d 纠错显著不同, 其余对齐。"""
    win = _window(80)
    snap_bar = {"X": win[-2]}
    reg = _registry(win[-1].timestamp)

    old = CrossSectionBuilder.build_cross_section(
        win[-1].timestamp, snap_bar, reg, bar_history={"X": win[:-1]},
    )[0]
    pre = {"X": FeatureEngineSnapshotSource().features_for("X", win)}
    new = CrossSectionBuilder.build_cross_section(
        win[-1].timestamp, snap_bar, reg, precomputed_features=pre,
    )[0]

    # return_20d: 旧用最旧值(~78日), 新是真 20 日 → 显著不同
    assert abs(new.return_20d - old.return_20d) > 0.01

    # 其余技术字段口径对齐(feature_engine 语义对齐手写版; macd 为 ~1e-6 EMA 近似差另算)
    for col in ("return_5d", "return_60d", "volatility_20d", "volatility_60d",
                "rsi_14", "ma_5", "ma_20", "ma_60", "atr_14", "skewness_20d",
                "high_20d", "low_20d", "avg_turnover_20d", "turnover_rate",
                "illiquidity_20d", "obv_slope_20d"):
        ov, nv = getattr(old, col), getattr(new, col)
        if ov is None or nv is None:
            continue
        assert nv == pytest.approx(ov, rel=1e-6, abs=1e-9), f"{col} 不应变"
    # macd: 全历史 EMA vs 窗口重启, ~1e-3 内
    if old.macd is not None and new.macd is not None:
        assert new.macd == pytest.approx(old.macd, abs=1e-2)
