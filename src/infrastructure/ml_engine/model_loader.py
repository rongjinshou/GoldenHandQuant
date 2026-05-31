from pathlib import Path
from typing import Any


class ModelLoader:
    """加载预训练 ML 模型文件（CatBoost .cbm / XGBoost .json）。"""

    def __init__(self, model_dir: str = "models/") -> None:
        self._model_dir = Path(model_dir)
        self._cache: dict[str, tuple[Any, float]] = {}  # {name: (model, file_mtime)}

    def _is_cache_valid(self, model_name: str, path: Path) -> bool:
        """Issue #6 (NEW-M11): 基于文件修改时间检查缓存是否仍有效。"""
        if model_name not in self._cache:
            return False
        _, cached_mtime = self._cache[model_name]
        return path.exists() and path.stat().st_mtime == cached_mtime

    def load_catboost(self, model_name: str) -> Any:
        """加载 CatBoost 模型（基于文件 mtime 的缓存失效）。"""
        import catboost
        path = self._model_dir / f"{model_name}.cbm"
        if not self._is_cache_valid(model_name, path):
            if not path.exists():
                raise FileNotFoundError(f"Model file not found: {path}")
            self._cache[model_name] = (
                catboost.CatBoostClassifier().load_model(str(path)),
                path.stat().st_mtime,
            )
        return self._cache[model_name][0]

    def load_xgboost(self, model_name: str) -> Any:
        """加载 XGBoost 模型（基于文件 mtime 的缓存失效）。"""
        import xgboost as xgb
        path = self._model_dir / f"{model_name}.json"
        if not self._is_cache_valid(model_name, path):
            if not path.exists():
                raise FileNotFoundError(f"Model file not found: {path}")
            model = xgb.XGBClassifier()
            model.load_model(str(path))
            self._cache[model_name] = (model, path.stat().st_mtime)
        return self._cache[model_name][0]

    def load_lightgbm(self, model_name: str) -> Any:
        """加载 LightGBM 模型（基于文件 mtime 的缓存失效）。"""
        path = self._model_dir / model_name / "model.joblib"
        if not path.exists():
            # 回退到旧路径格式
            path = self._model_dir / f"{model_name}.pkl"
        if not self._is_cache_valid(model_name, path):
            if not path.exists():
                raise FileNotFoundError(f"Model file not found: {path}")
            import joblib
            self._cache[model_name] = (joblib.load(str(path)), path.stat().st_mtime)
        return self._cache[model_name][0]
