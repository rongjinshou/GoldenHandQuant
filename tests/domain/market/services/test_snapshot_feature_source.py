"""FeatureEngineSnapshotSource golden 等价 — == feature_engine 末行技术列。"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.domain.market.services.feature_engine import (
    TECHNICAL_COLUMNS,
    compute_symbol_features,
)
from src.domain.market.services.snapshot_feature_source import (
    FeatureEngineFeatureSource,
    FeatureEngineSnapshotSource,
    StoredFeatureSource,
)
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe


def _window(n: int) -> list[Bar]:
    base = datetime(2024, 1, 1)
    bars, prev = [], 0.0
    for i in range(n):
        c = 10.0 + i * 0.1 + (i % 5) * 0.3 - (i % 7) * 0.2  # 有涨有跌
        bars.append(Bar(
            symbol="X", timeframe=Timeframe.DAY_1,
            timestamp=base + timedelta(days=i),
            open=c - 0.1, high=c + 0.25, low=c - 0.2, close=c,
            volume=1000.0 + (i % 9) * 50, prev_close=prev or c,
        ))
        prev = c
    return bars


def _df(bars: list[Bar]) -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": [b.symbol for b in bars],
        "date": [b.timestamp for b in bars],
        "open": [b.open for b in bars], "high": [b.high for b in bars],
        "low": [b.low for b in bars], "close": [b.close for b in bars],
        "volume": [b.volume for b in bars], "prev_close": [b.prev_close for b in bars],
    })


@pytest.mark.parametrize("n", [80, 40, 36])
def test_features_for_matches_feature_engine_last_row(n: int):
    bars = _window(n)
    got = FeatureEngineSnapshotSource().features_for("X", bars)

    last = compute_symbol_features(_df(bars)).iloc[-1]
    for col in TECHNICAL_COLUMNS:
        if pd.isna(last[col]):
            assert col not in got, f"{col} 应缺失"
        else:
            assert got[col] == pytest.approx(float(last[col]), abs=1e-12), col


def test_short_window_returns_empty():
    assert FeatureEngineSnapshotSource().features_for("X", _window(1)) == {}


def test_feature_engine_feature_source_delegates_per_symbol():
    win = _window(40)
    windows = {"X": win, "Y": win}
    out = FeatureEngineFeatureSource().features_for(
        datetime(2024, 3, 1), ["X", "Y"], windows
    )
    expect = FeatureEngineSnapshotSource().features_for("X", win)
    assert out["X"] == expect and out["Y"] == expect


def test_stored_feature_source_reads_by_date_symbol():
    df = pd.DataFrame([
        {"date": pd.Timestamp("2024-06-04"), "symbol": "A", "return_20d": 0.12, "rsi_14": 55.0},
        {"date": pd.Timestamp("2024-06-04"), "symbol": "B", "return_20d": float("nan"), "rsi_14": 60.0},
        {"date": pd.Timestamp("2024-06-05"), "symbol": "A", "return_20d": 0.05, "rsi_14": 50.0},
    ])
    src = StoredFeatureSource(df)
    out = src.features_for(datetime(2024, 6, 4), ["A", "B"], {})
    assert out["A"] == {"return_20d": 0.12, "rsi_14": 55.0}
    assert out["B"] == {"rsi_14": 60.0}      # NaN return_20d 略去
    assert src.features_for(datetime(2024, 6, 4), ["A"], {}) == {"A": {"return_20d": 0.12, "rsi_14": 55.0}}
    assert src.features_for(datetime(2024, 6, 6), ["A"], {}) == {}   # 无该日
