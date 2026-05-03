import numpy as np

from src.infrastructure.ml_engine.model_loader import ModelLoader


class InferenceEngine:
    """ML 模型批量推理引擎。

    将模型预测结果（涨跌概率）转换为 Signal 可消费的方向建议。
    """

    def __init__(self, model_loader: ModelLoader) -> None:
        self._loader = model_loader

    def predict(self, model_name: str, features: np.ndarray) -> np.ndarray:
        """返回涨跌概率 [0, 1]，>0.5 表示看涨。"""
        model = self._loader.load_catboost(model_name)
        proba = model.predict_proba(features)
        return proba[:, 1] if proba.shape[1] > 1 else proba[:, 0]

    def predict_batch(
        self, model_name: str, feature_dict: dict[str, np.ndarray]
    ) -> dict[str, float]:
        """批量预测多个标的，返回 symbol -> probability 映射。"""
        results: dict[str, float] = {}
        for symbol, features in feature_dict.items():
            if features.size > 0:
                results[symbol] = float(self.predict(model_name, features.reshape(1, -1))[0])
        return results
