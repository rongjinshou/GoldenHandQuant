"""测试数据集构建器。"""

from datetime import datetime

import numpy as np
import pandas as pd

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.infrastructure.ml_engine.dataset_builder import DatasetBuilder, DatasetConfig


def _make_snapshot(symbol: str, date: datetime, close: float, **kwargs) -> StockSnapshot:
    defaults = dict(
        symbol=symbol, date=date,
        open=close, high=close * 1.02, low=close * 0.98,
        close=close, volume=1e6,
        name="Test", list_date=datetime(2020, 1, 1), market_cap=1e10,
        return_5d=0.01, rsi_14=50.0, pe_ratio=15.0,
    )
    defaults.update(kwargs)
    return StockSnapshot(**defaults)


class TestDatasetBuilder:
    def test_build_produces_dataframe(self) -> None:
        dates = [datetime(2025, 1, i) for i in range(1, 21)]
        snapshots_by_date: dict = {}
        price_series: dict[str, pd.Series] = {}

        prices_a = []
        prices_b = []
        for d in dates:
            close_a = 10.0 + np.random.randn() * 0.1
            close_b = 20.0 + np.random.randn() * 0.1
            prices_a.append(close_a)
            prices_b.append(close_b)
            snapshots_by_date[d] = [
                _make_snapshot("A", d, close_a),
                _make_snapshot("B", d, close_b),
            ]

        price_series["A"] = pd.Series(prices_a, index=dates)
        price_series["B"] = pd.Series(prices_b, index=dates)

        config = DatasetConfig(label_horizon=3, winsorize_quantile=0.0, min_history_days=1)
        builder = DatasetBuilder(config)
        df = builder.build(snapshots_by_date, price_series)

        assert not df.empty
        assert "date" in df.columns
        assert "symbol" in df.columns
        assert "label" in df.columns
        assert df["label"].notna().all()

    def test_build_drops_nan_labels(self) -> None:
        dates = [datetime(2025, 1, i) for i in range(1, 6)]
        snapshots_by_date = {}
        price_series = {}

        for d in dates:
            snapshots_by_date[d] = [_make_snapshot("A", d, 10.0)]
        # 价格序列太短，标签会是 NaN
        price_series["A"] = pd.Series([10.0] * 5, index=dates)

        config = DatasetConfig(label_horizon=10, winsorize_quantile=0.0, min_history_days=1)
        builder = DatasetBuilder(config)
        df = builder.build(snapshots_by_date, price_series)

        # 所有标签都是 NaN（horizon=10 但只有 5 天数据），应返回空
        assert df.empty or df["label"].notna().all()

    def test_save_and_load_parquet(self, tmp_path) -> None:
        df = pd.DataFrame({"date": [datetime(2025, 1, 1)], "symbol": ["A"], "f1": [1.0], "label": [0.05]})
        path = str(tmp_path / "test.parquet")
        DatasetBuilder.save(df, path)
        loaded = DatasetBuilder.load(path)
        assert len(loaded) == 1
        assert loaded.iloc[0]["f1"] == 1.0
