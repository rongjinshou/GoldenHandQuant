"""模型版本管理。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, kw_only=True)
class ModelMetadata:
    """模型元信息。"""
    model_name: str
    model_type: str
    created_at: str
    train_period: str
    eval_period: str
    label_horizon: int
    feature_count: int
    train_samples: int
    best_params: dict
    cv_metrics: dict
    features: list[str]
    model_path: str


class ModelRegistry:
    """模型版本管理。"""

    def __init__(self, models_dir: str = "models/") -> None:
        self._models_dir = Path(models_dir)
        self._models_dir.mkdir(parents=True, exist_ok=True)
        self._registry_path = self._models_dir / "registry.json"

    def register(self, metadata: ModelMetadata) -> None:
        """注册新模型版本。"""
        registry = self._load_registry()
        registry[metadata.model_name] = {
            "model_name": metadata.model_name,
            "model_type": metadata.model_type,
            "created_at": metadata.created_at,
            "train_period": metadata.train_period,
            "eval_period": metadata.eval_period,
            "label_horizon": metadata.label_horizon,
            "feature_count": metadata.feature_count,
            "train_samples": metadata.train_samples,
            "best_params": metadata.best_params,
            "cv_metrics": metadata.cv_metrics,
            "features": metadata.features,
            "model_path": metadata.model_path,
        }
        self._save_registry(registry)

    def get_latest(self, model_name: str) -> ModelMetadata:
        """获取指定模型的元信息。"""
        registry = self._load_registry()
        if model_name not in registry:
            raise KeyError(f"Model not found: {model_name}")
        return self._to_metadata(registry[model_name])

    def list_models(self) -> list[ModelMetadata]:
        """列出所有已注册模型。"""
        registry = self._load_registry()
        return [self._to_metadata(v) for v in registry.values()]

    def get_model_path(self, model_name: str, version: str = "latest") -> str:
        """获取模型文件路径。"""
        meta = self.get_latest(model_name)
        return meta.model_path

    def _load_registry(self) -> dict:
        if self._registry_path.exists():
            return json.loads(self._registry_path.read_text())
        return {}

    def _save_registry(self, registry: dict) -> None:
        self._registry_path.write_text(json.dumps(registry, indent=2, default=str))

    @staticmethod
    def _to_metadata(data: dict) -> ModelMetadata:
        return ModelMetadata(
            model_name=data["model_name"],
            model_type=data.get("model_type", "lightgbm"),
            created_at=data.get("created_at", ""),
            train_period=data.get("train_period", ""),
            eval_period=data.get("eval_period", ""),
            label_horizon=data.get("label_horizon", 5),
            feature_count=data.get("feature_count", 0),
            train_samples=data.get("train_samples", 0),
            best_params=data.get("best_params", {}),
            cv_metrics=data.get("cv_metrics", {}),
            features=data.get("feature_columns", data.get("features", [])),
            model_path=data.get("model_path", ""),
        )
