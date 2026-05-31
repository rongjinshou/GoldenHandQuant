"""测试衍生特征计算和截面标准化。"""

import math
from datetime import datetime

import numpy as np
import pandas as pd

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.infrastructure.ml_engine.feature_transforms import (
    compute_derived_features,
    cross_section_standardize,
    extract_base_features,
)


def _make_snapshot(**kwargs) -> StockSnapshot:
    defaults = dict(
        symbol="600000.SH", date=datetime(2025, 1, 15),
        open=10.0, high=10.5, low=9.5, close=10.0, volume=1e6,
        name="Test", list_date=datetime(2020, 1, 1), market_cap=1e10,
    )
    defaults.update(kwargs)
    return StockSnapshot(**defaults)


class TestExtractBaseFeatures:
    def test_extracts_known_fields(self) -> None:
        snap = _make_snapshot(return_5d=0.05, rsi_14=60.0, pe_ratio=15.0)
        features = extract_base_features(snap)
        assert features["return_5d"] == 0.05
        assert features["rsi_14"] == 60.0
        assert features["pe_ratio"] == 15.0
        assert features["symbol"] == "600000.SH"

    def test_missing_fields_are_none(self) -> None:
        snap = _make_snapshot()
        features = extract_base_features(snap)
        assert features["macd"] is None
        assert features["volatility_20d"] is None


class TestComputeDerivedFeatures:
    def test_close_to_ma5(self) -> None:
        row = {"close": 10.0, "ma_5": 9.5, "ma_20": None, "ma_60": None,
               "high_20d": None, "low_20d": None, "macd": None, "macd_signal": None,
               "pb_ratio": None, "market_cap": None, "volatility_20d": None,
               "turnover_rate": None, "avg_turnover_20d": None}
        result = compute_derived_features([row])
        assert result[0]["close_to_ma5"] is not None
        assert abs(result[0]["close_to_ma5"] - (10.0 / 9.5 - 1.0)) < 1e-6

    def test_macd_hist(self) -> None:
        row = {"close": None, "ma_5": None, "ma_20": None, "ma_60": None,
               "high_20d": None, "low_20d": None, "macd": 0.5, "macd_signal": 0.2,
               "pb_ratio": None, "market_cap": None, "volatility_20d": None,
               "turnover_rate": None, "avg_turnover_20d": None}
        result = compute_derived_features([row])
        assert abs(result[0]["macd_hist"] - 0.3) < 1e-6

    def test_log_market_cap(self) -> None:
        row = {"close": None, "ma_5": None, "ma_20": None, "ma_60": None,
               "high_20d": None, "low_20d": None, "macd": None, "macd_signal": None,
               "pb_ratio": None, "market_cap": math.e, "volatility_20d": None,
               "turnover_rate": None, "avg_turnover_20d": None}
        result = compute_derived_features([row])
        assert abs(result[0]["log_market_cap"] - 1.0) < 1e-6

    def test_bp_ratio(self) -> None:
        row = {"close": None, "ma_5": None, "ma_20": None, "ma_60": None,
               "high_20d": None, "low_20d": None, "macd": None, "macd_signal": None,
               "pb_ratio": 2.0, "market_cap": None, "volatility_20d": None,
               "turnover_rate": None, "avg_turnover_20d": None}
        result = compute_derived_features([row])
        assert abs(result[0]["bp_ratio"] - 0.5) < 1e-6

    def test_high_low_range_and_close_position(self) -> None:
        row = {"close": 10.0, "ma_5": None, "ma_20": None, "ma_60": None,
               "high_20d": 12.0, "low_20d": 8.0, "macd": None, "macd_signal": None,
               "pb_ratio": None, "market_cap": None, "volatility_20d": None,
               "turnover_rate": None, "avg_turnover_20d": None}
        result = compute_derived_features([row])
        assert abs(result[0]["high_low_range"] - 0.4) < 1e-6  # (12-8)/10
        assert abs(result[0]["close_position"] - 0.5) < 1e-6  # (10-8)/(12-8)

    def test_turnover_relative_deviation(self) -> None:
        row = {"close": None, "ma_5": None, "ma_20": None, "ma_60": None,
               "high_20d": None, "low_20d": None, "macd": None, "macd_signal": None,
               "pb_ratio": None, "market_cap": None, "volatility_20d": None,
               "turnover_rate": 2.0, "avg_turnover_20d": 1.0}
        result = compute_derived_features([row])
        assert abs(result[0]["turnover_relative_deviation"] - 1.0) < 1e-6


class TestCrossSectionStandardize:
    def test_standardize_to_zero_mean_unit_var(self) -> None:
        df = pd.DataFrame({
            "date": ["2025-01-01"] * 4 + ["2025-01-02"] * 4,
            "symbol": ["A", "B", "C", "D"] * 2,
            "f1": [1.0, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0, 40.0],
        })
        cross_section_standardize(df, ["f1"])

        # 每日截面内标准化后均值约 0
        g1 = df[df["date"] == "2025-01-01"]["f1"]
        g2 = df[df["date"] == "2025-01-02"]["f1"]
        assert abs(g1.mean()) < 1e-6
        assert abs(g2.mean()) < 1e-6
