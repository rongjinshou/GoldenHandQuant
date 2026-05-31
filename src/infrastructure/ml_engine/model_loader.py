from pathlib import Path
from typing import Any


class ModelLoader:
    """加载预训练 ML 模型文件（CatBoost .cbm / XGBoost .json）。"""

    def __init__(self, model_dir: str = "models/") -> None:
        self._model_dir = Path(model_dir)
        self._cache: dict[str, Any] = {}

    def load_catboost(self, model_name: str) -> Any:
        """加载 CatBoost 模型（惰性缓存）。"""
        import catboost
        if model_name not in self._cache:
            path = self._model_dir / f"{model_name}.cbm"
            if not path.exists():
                raise FileNotFoundError(f"Model file not found: {path}")
            self._cache[model_name] = catboost.CatBoostClassifier().load_model(str(path))
        return self._cache[model_name]

    def load_xgboost(self, model_name: str) -> Any:
        """加载 XGBoost 模型（惰性缓存）。"""
        import xgboost as xgb
        if model_name not in self._cache:
            path = self._model_dir / f"{model_name}.json"
            if not path.exists():
                raise FileNotFoundError(f"Model file not found: {path}")
            model = xgb.XGBClassifier()
            model.load_model(str(path))
            self._cache[model_name] = model
        return self._cache[model_name]

    def load_lightgbm(self, model_name: str) -> Any:
        """加载 LightGBM 模型（惰性缓存）。"""
        if model_name not in self._cache:
            path = self._model_dir / model_name / "model.joblib"
            if not path.exists():
                # 回退到旧路径格式
                path = self._model_dir / f"{model_name}.pkl"
            if not path.exists():
                raise FileNotFoundError(f"Model file not found: {path}")
            import joblib
            self._cache[model_name] = joblib.load(str(path))
        return self._cache[model_name]
