"""测试 LightGBM 训练器。"""

import numpy as np
import pandas as pd
import pytest

from src.infrastructure.ml_engine.trainer import LightGBMTrainer, TrainConfig


def _make_dataset(n: int = 500, n_features: int = 5) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.bdate_range("2022-01-01", periods=n // 5)
    rows = []
    for d in dates:
        for i in range(5):
            features = {f"f{j}": np.random.randn() for j in range(n_features)}
            features["date"] = d
            features["symbol"] = f"S{i}"
            features["label"] = np.random.randn() * 0.02
            rows.append(features)
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def _clean_models(tmp_path, monkeypatch):
    """将模型保存目录重定向到临时目录。"""
    monkeypatch.chdir(tmp_path)


class TestLightGBMTrainer:
    def test_train_returns_result(self) -> None:
        df = _make_dataset(500, 5)
        config = TrainConfig(
            model_name="test_model",
            n_optuna_trials=2,
            n_cv_splits=2,
            early_stopping_rounds=10,
            random_seed=42,
        )
        trainer = LightGBMTrainer(config)
        result = trainer.train(df)

        assert result.model_name == "test_model"
        assert result.train_samples > 0
        assert result.feature_count == 5
        assert isinstance(result.mean_ic, float)
        assert isinstance(result.ic_ir, float)
        assert len(result.best_params) > 0
        assert len(result.cv_metrics) > 0

    def test_model_file_created(self) -> None:
        df = _make_dataset(500, 5)
        config = TrainConfig(
            model_name="test_model",
            n_optuna_trials=2,
            n_cv_splits=2,
            early_stopping_rounds=10,
        )
        trainer = LightGBMTrainer(config)
        result = trainer.train(df)

        from pathlib import Path
        assert Path(result.model_path).exists()

    def test_feature_importance_non_empty(self) -> None:
        df = _make_dataset(500, 5)
        config = TrainConfig(
            model_name="test_model",
            n_optuna_trials=2,
            n_cv_splits=2,
            early_stopping_rounds=10,
        )
        trainer = LightGBMTrainer(config)
        result = trainer.train(df)

        assert len(result.feature_importance) == 5
        assert all(v >= 0 for v in result.feature_importance.values())

    def test_mean_ic_is_finite(self) -> None:
        df = _make_dataset(500, 5)
        config = TrainConfig(
            model_name="test_model",
            n_optuna_trials=2,
            n_cv_splits=2,
            early_stopping_rounds=10,
        )
        trainer = LightGBMTrainer(config)
        result = trainer.train(df)

        assert np.isfinite(result.mean_ic)
        assert np.isfinite(result.ic_ir)
