"""测试模型注册表。"""

from src.infrastructure.ml_engine.model_registry import ModelMetadata, ModelRegistry


def _make_metadata(model_name: str = "test_model") -> ModelMetadata:
    return ModelMetadata(
        model_name=model_name,
        model_type="lightgbm",
        created_at="2025-01-01T00:00:00",
        train_period="2020-01-01 ~ 2024-12-31",
        eval_period="2025-01-01 ~ 2025-06-30",
        label_horizon=5,
        feature_count=30,
        train_samples=10000,
        best_params={"n_estimators": 100, "learning_rate": 0.05},
        cv_metrics={"mean_ic": 0.06, "ic_ir": 0.5},
        features=["f1", "f2", "f3"],
        model_path="models/test_model/model.joblib",
    )


class TestModelRegistry:
    def test_register_and_get_latest(self, tmp_path) -> None:
        registry = ModelRegistry(models_dir=str(tmp_path))
        metadata = _make_metadata()
        registry.register(metadata)

        loaded = registry.get_latest("test_model")
        assert loaded.model_name == "test_model"
        assert loaded.model_type == "lightgbm"
        assert loaded.feature_count == 30

    def test_list_models(self, tmp_path) -> None:
        registry = ModelRegistry(models_dir=str(tmp_path))
        registry.register(_make_metadata("model_a"))
        registry.register(_make_metadata("model_b"))

        models = registry.list_models()
        names = {m.model_name for m in models}
        assert "model_a" in names
        assert "model_b" in names

    def test_get_latest_unknown_raises(self, tmp_path) -> None:
        registry = ModelRegistry(models_dir=str(tmp_path))
        try:
            registry.get_latest("nonexistent")
            assert False, "Should have raised KeyError"
        except KeyError:
            pass

    def test_get_model_path(self, tmp_path) -> None:
        registry = ModelRegistry(models_dir=str(tmp_path))
        registry.register(_make_metadata())

        path = registry.get_model_path("test_model")
        assert path == "models/test_model/model.joblib"
