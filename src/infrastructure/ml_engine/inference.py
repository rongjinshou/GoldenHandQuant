import numpy as np

from src.infrastructure.ml_engine.model_loader import ModelLoader


class InferenceEngine:
    """ML 模型批量推理引擎。

    支持 CatBoost（分类）和 LightGBM（回归）两种模型类型。
    """

    def __init__(self, model_loader: ModelLoader, model_type: str = "catboost") -> None:
        self._loader = model_loader
        self._model_type = model_type

    def predict(self, model_name: str, features: np.ndarray) -> np.ndarray:
        """预测。CatBoost 返回概率，LightGBM 返回回归分数。"""
        if self._model_type == "lightgbm":
            model = self._loader.load_lightgbm(model_name)
            return model.predict(features)
        # 默认 CatBoost 分类
        model = self._loader.load_catboost(model_name)
        proba = model.predict_proba(features)
        return proba[:, 1] if proba.shape[1] > 1 else proba[:, 0]

    def predict_batch(
        self, model_name: str, feature_dict: dict[str, np.ndarray]
    ) -> dict[str, float]:
        """批量预测多个标的，返回 symbol -> score 映射。"""
        results: dict[str, float] = {}
        for symbol, features in feature_dict.items():
            if features.size > 0:
                results[symbol] = float(self.predict(model_name, features.reshape(1, -1))[0])
        return results
