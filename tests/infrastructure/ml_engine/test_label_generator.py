"""测试标签生成器。"""

import numpy as np
import pandas as pd

from src.infrastructure.ml_engine.label_generator import LabelConfig, generate_labels


class TestGenerateLabels:
    def test_basic_forward_return(self) -> None:
        dates = pd.date_range("2025-01-01", periods=10, freq="B")
        prices = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109], index=dates)
        df = pd.DataFrame({"date": dates, "symbol": "A"})
        config = LabelConfig(horizon=5, winsorize_quantile=0.0)
        labels = generate_labels(df, {"A": prices}, config)

        # 第 0 天 label = close[5]/close[0] - 1 = 105/100 - 1 = 0.05
        assert abs(labels.iloc[0] - 0.05) < 1e-6
        # 最后 5 天 label 为 NaN（不足 horizon 天后数据）
        assert np.isnan(labels.iloc[9])

    def test_winsorize_clips_extremes(self) -> None:
        dates = pd.date_range("2025-01-01", periods=20, freq="B")
        prices = list(range(100, 120))
        prices[15] = 1000  # 极端值
        prices_series = pd.Series(prices, index=dates)
        df = pd.DataFrame({"date": dates, "symbol": "A"})
        config = LabelConfig(horizon=5, winsorize_quantile=0.05)
        labels = generate_labels(df, {"A": prices_series}, config)

        # 极端值应被裁剪
        valid = labels.dropna()
        assert valid.max() < 10.0  # 原始极端值会被裁剪

    def test_missing_symbol_gets_nan(self) -> None:
        dates = pd.date_range("2025-01-01", periods=10, freq="B")
        df = pd.DataFrame({"date": dates, "symbol": "B"})
        config = LabelConfig(horizon=5, winsorize_quantile=0.0)
        labels = generate_labels(df, {"A": pd.Series([100] * 10, index=dates)}, config)
        assert labels.isna().all()

    def test_multi_symbol_labels(self) -> None:
        dates = pd.date_range("2025-01-01", periods=10, freq="B")
        df = pd.DataFrame({
            "date": list(dates) * 2,
            "symbol": ["A"] * 10 + ["B"] * 10,
        })
        prices_a = pd.Series(range(100, 110), index=dates)
        prices_b = pd.Series(range(200, 210), index=dates)
        config = LabelConfig(horizon=5, winsorize_quantile=0.0)
        labels = generate_labels(df, {"A": prices_a, "B": prices_b}, config)

        assert len(labels) == 20
        assert not labels.iloc[:5].isna().any()
