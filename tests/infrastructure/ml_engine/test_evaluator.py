"""测试模型评估器。"""

import numpy as np
import pandas as pd

from src.infrastructure.ml_engine.evaluator import (
    ModelEvaluator,
)


def _make_predictions(n_dates: int = 20, n_symbols: int = 10, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    dates = pd.bdate_range("2025-01-01", periods=n_dates)
    rows = []
    for d in dates:
        for i in range(n_symbols):
            pred = np.random.randn()
            actual = pred * 0.3 + np.random.randn() * 0.7  # 弱相关
            rows.append({"date": d, "symbol": f"S{i}", "pred": pred, "actual": actual})
    return pd.DataFrame(rows)


class TestModelEvaluator:
    def test_evaluate_predictions_metrics(self) -> None:
        evaluator = ModelEvaluator()
        df = _make_predictions()
        metrics = evaluator.evaluate_predictions(df)

        assert -1.0 <= metrics.ic <= 1.0
        assert isinstance(metrics.ic_ir, float)
        assert 0.0 <= metrics.ic_positive_ratio <= 1.0

    def test_perfect_correlation_gives_high_ic(self) -> None:
        evaluator = ModelEvaluator()
        dates = pd.bdate_range("2025-01-01", periods=10)
        rows = []
        for d in dates:
            for i in range(10):
                v = float(i)
                rows.append({"date": d, "symbol": f"S{i}", "pred": v, "actual": v})
        df = pd.DataFrame(rows)
        metrics = evaluator.evaluate_predictions(df)
        assert metrics.ic > 0.9  # 完美相关

    def test_evaluate_quintiles_returns_n_results(self) -> None:
        evaluator = ModelEvaluator()
        df = _make_predictions(n_dates=30, n_symbols=20)
        results = evaluator.evaluate_quintiles(df, {}, n_quintiles=5)
        assert len(results) == 5
        for qr in results:
            assert 1 <= qr.quintile <= 5

    def test_full_evaluation_report(self) -> None:
        evaluator = ModelEvaluator()
        df = _make_predictions()
        report = evaluator.full_evaluation("test_model", df, {})

        assert report.model_name == "test_model"
        assert report.prediction_metrics is not None
        assert len(report.quintile_results) == 5
        assert isinstance(report.long_short_return, float)

    def test_empty_predictions_handled(self) -> None:
        evaluator = ModelEvaluator()
        df = pd.DataFrame(columns=["date", "symbol", "pred", "actual"])
        metrics = evaluator.evaluate_predictions(df)
        assert metrics.ic == 0.0
