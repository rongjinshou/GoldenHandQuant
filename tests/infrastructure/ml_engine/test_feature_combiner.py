"""AutoFeatureCombiner 单元测试。"""

from datetime import datetime

import numpy as np

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.infrastructure.ml_engine.feature_combiner import (
    AutoFeatureCombiner,
    FeatureOperator,
    _safe_div,
)


def _make_snapshot(symbol: str, **kwargs) -> StockSnapshot:
    defaults = dict(
        symbol=symbol,
        date=datetime(2024, 6, 15),
        open=10.0, high=11.0, low=9.0, close=10.5,
        volume=100000.0, name=f"Stock {symbol}",
        list_date=datetime(2000, 1, 1),
        market_cap=1e10,
        pe_ratio=15.0, pb_ratio=2.0,
        roe_ttm=0.15, return_5d=0.02, return_20d=0.05,
        volatility_20d=0.03, turnover_rate=1.2,
        rsi_14=55.0, macd=0.1, macd_signal=0.05,
    )
    defaults.update(kwargs)
    return StockSnapshot(**defaults)


class TestSafeDiv:
    def test_normal_division(self):
        a = np.array([10.0, 20.0, 30.0])
        b = np.array([2.0, 4.0, 5.0])
        result = _safe_div(a, b)
        np.testing.assert_array_almost_equal(result, [5.0, 5.0, 6.0])

    def test_zero_denominator_returns_nan(self):
        a = np.array([10.0, 20.0])
        b = np.array([0.0, 5.0])
        result = _safe_div(a, b)
        assert np.isnan(result[0])
        assert result[1] == 4.0


class TestAutoFeatureCombiner:
    def test_empty_snapshots_returns_empty_df(self):
        combiner = AutoFeatureCombiner()
        result = combiner.generate_combinations([])
        assert result.empty

    def test_generates_base_features(self):
        combiner = AutoFeatureCombiner()
        snapshots = [_make_snapshot("000001"), _make_snapshot("000002")]
        df = combiner.generate_combinations(snapshots)
        assert not df.empty
        assert "pe_ratio" in df.columns
        assert "return_5d" in df.columns
        assert len(df) == 2

    def test_generates_combination_features(self):
        combiner = AutoFeatureCombiner()
        snapshots = [_make_snapshot(f"{i:06d}") for i in range(50)]
        df = combiner.generate_combinations(snapshots, strategy="standard")
        # 应有基础特征 + 组合特征
        assert len(df.columns) > 50
        # 检查组合特征存在
        rank_cols = [c for c in df.columns if c.startswith("rank_")]
        assert len(rank_cols) > 0

    def test_conservative_fewer_than_standard(self):
        combiner_c = AutoFeatureCombiner()
        combiner_s = AutoFeatureCombiner()
        snapshots = [_make_snapshot(f"{i:06d}") for i in range(50)]
        df_c = combiner_c.generate_combinations(snapshots, strategy="conservative")
        df_s = combiner_s.generate_combinations(snapshots, strategy="standard")
        assert len(df_c.columns) < len(df_s.columns)

    def test_aggressive_more_than_standard(self):
        combiner_a = AutoFeatureCombiner()
        combiner_s = AutoFeatureCombiner()
        snapshots = [_make_snapshot(f"{i:06d}") for i in range(50)]
        df_a = combiner_a.generate_combinations(snapshots, strategy="aggressive")
        df_s = combiner_s.generate_combinations(snapshots, strategy="standard")
        assert len(df_a.columns) > len(df_s.columns)

    def test_no_duplicate_column_names(self):
        combiner = AutoFeatureCombiner()
        snapshots = [_make_snapshot(f"{i:06d}") for i in range(50)]
        df = combiner.generate_combinations(snapshots)
        assert len(df.columns) == len(set(df.columns))

    def test_get_feature_names(self):
        combiner = AutoFeatureCombiner()
        snapshots = [_make_snapshot(f"{i:06d}") for i in range(10)]
        combiner.generate_combinations(snapshots)
        names = combiner.get_feature_names()
        assert len(names) > 0
        assert "pe_ratio" in names

    def test_get_expression(self):
        combiner = AutoFeatureCombiner()
        snapshots = [_make_snapshot(f"{i:06d}") for i in range(50)]
        combiner.generate_combinations(snapshots)
        names = combiner.get_feature_names()
        rank_names = [n for n in names if n.startswith("rank_")]
        if rank_names:
            expr = combiner.get_expression(rank_names[0])
            assert "rank" in expr

    def test_rank_operator(self):
        values = np.array([3.0, 1.0, 2.0, np.nan, 5.0, 4.0])
        result = AutoFeatureCombiner._apply_unary(values, FeatureOperator.RANK)
        # 非 NaN 值应有排名
        valid = result[~np.isnan(values)]
        assert len(valid) == 5
        assert valid.min() >= 0.0
        assert valid.max() <= 1.0

    def test_zscore_operator(self):
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = AutoFeatureCombiner._apply_unary(values, FeatureOperator.ZSCORE)
        assert abs(result.mean()) < 0.01  # 均值约 0

    def test_all_nan_values(self):
        combiner = AutoFeatureCombiner()
        snap = _make_snapshot("000001", pe_ratio=None, return_5d=None, volatility_20d=None)
        df = combiner.generate_combinations([snap])
        # 应能生成，只是值为 NaN
        assert len(df) == 1
