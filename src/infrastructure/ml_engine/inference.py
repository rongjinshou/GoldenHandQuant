import numpy as np

from src.infrastructure.ml_engine.model_loader import ModelLoader


class InferenceEngine:
    """ML 模型批量推理引擎。

    支持 CatBoost（分类）和 LightGBM（回归）两种模型类型。
    """

    def __init__(
        self,
        model_loader: ModelLoader,
        model_type: str = "catboost",
        standardize: bool = False,
    ) -> None:
        self._loader = model_loader
        self._model_type = model_type
        self._standardize = standardize

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
        """批量预测多个标的，返回 symbol -> score 映射。

        当 standardize=True 时，对所有标的的特征做截面 Z-score 标准化后再推理。
        """
        if not feature_dict:
            return {}

        symbols = list(feature_dict.keys())
        matrix = np.vstack([np.asarray(feature_dict[s], dtype=np.float64).reshape(1, -1) for s in symbols])

        if self._standardize:
            matrix = self._cross_section_standardize(matrix)

        results: dict[str, float] = {}
        for i, symbol in enumerate(symbols):
            row = matrix[i]
            if row.size > 0:
                results[symbol] = float(self.predict(model_name, row.reshape(1, -1))[0])
        return results

    @staticmethod
    def _cross_section_standardize(matrix: np.ndarray) -> np.ndarray:
        """截面 Z-score 标准化，与 dataset_builder 的逻辑一致。"""
        mean = np.nanmean(matrix, axis=0)
        std = np.nanstd(matrix, axis=0)
        std[std < 1e-10] = 1.0  # 避免除零
        return (matrix - mean) / std
