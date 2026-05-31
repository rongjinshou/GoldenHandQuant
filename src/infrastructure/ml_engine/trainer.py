"""LightGBM 训练器，集成 Optuna 超参优化 + 时间序列 CV。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.infrastructure.ml_engine.time_series_cv import PurgedWalkForwardCV, TimeSeriesCVConfig

logger = logging.getLogger(__name__)

# 非特征列
_NON_FEATURE_COLS = {"date", "symbol", "label", "actual_return"}


@dataclass(slots=True, kw_only=True)
class TrainConfig:
    """训练配置。"""
    model_name: str
    n_optuna_trials: int = 50
    n_cv_splits: int = 5
    early_stopping_rounds: int = 50
    random_seed: int = 42
    feature_columns: list[str] = field(default_factory=list)
    label_column: str = "label"
    lgbm_params: dict = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class TrainResult:
    """训练结果。"""
    model_name: str
    best_params: dict
    cv_metrics: list[dict]
    mean_ic: float
    ic_ir: float
    feature_importance: dict[str, float]
    model_path: str
    train_samples: int
    feature_count: int


class LightGBMTrainer:
    """LightGBM 训练器，集成 Optuna 超参优化 + 时间序列 CV。"""

    def __init__(self, config: TrainConfig) -> None:
        self._config = config

    def train(self, dataset: pd.DataFrame) -> TrainResult:
        """执行完整训练流程。"""
        import lightgbm as lgb
        import optuna

        config = self._config

        # 自动检测特征列
        feature_cols = config.feature_columns
        if not feature_cols:
            feature_cols = [
                c for c in dataset.columns
                if c not in _NON_FEATURE_COLS and dataset[c].dtype in ("float64", "float32", "int64")
            ]

        label_col = config.label_column

        # CV 切分
        cv_config = TimeSeriesCVConfig(
            n_splits=config.n_cv_splits,
            gap_days=5,
            min_train_days=200,
        )
        cv_splitter = PurgedWalkForwardCV(cv_config)
        folds = cv_splitter.split(dataset)

        if not folds:
            logger.warning("数据不足，无法生成 CV 折，使用全量训练")
            folds = [(dataset.index, dataset.index)]

        # Optuna 超参搜索
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=config.random_seed))
        study.optimize(
            lambda trial: self._objective(trial, dataset, folds, feature_cols, label_col, config),
            n_trials=config.n_optuna_trials,
            show_progress_bar=False,
        )

        best_params = study.best_params
        # 合并固定参数
        full_params = {
            "objective": "regression",
            "metric": "mse",
            "verbosity": -1,
            "boosting_type": "gbdt",
            "seed": config.random_seed,
            **best_params,
            **config.lgbm_params,
        }

        # 用最优参数在每折上训练，记录 CV 指标
        cv_metrics: list[dict] = []
        fold_ics: list[float] = []
        for train_idx, test_idx in folds:
            x_train = dataset.loc[train_idx, feature_cols]
            y_train = dataset.loc[train_idx, label_col]
            x_test = dataset.loc[test_idx, feature_cols]
            y_test = dataset.loc[test_idx, label_col]

            model = lgb.LGBMRegressor(**full_params)
            model.fit(
                x_train, y_train,
                eval_set=[(x_test, y_test)],
                callbacks=[lgb.early_stopping(config.early_stopping_rounds, verbose=False)],
            )
            preds = model.predict(x_test)
            ic, _ = spearmanr(preds, y_test)
            if np.isnan(ic):
                ic = 0.0
            fold_ics.append(ic)
            cv_metrics.append({"ic": ic, "n_test": len(test_idx)})

        mean_ic = float(np.mean(fold_ics))
        ic_std = float(np.std(fold_ics))
        ic_ir = mean_ic / ic_std if ic_std > 0 else 0.0

        # 用全部数据重新训练最终模型
        x_all = dataset[feature_cols]
        y_all = dataset[label_col]
        final_model = lgb.LGBMRegressor(**full_params)
        final_model.fit(x_all, y_all)

        # 特征重要性（gain）
        importances = dict(zip(feature_cols, final_model.feature_importances_.tolist()))

        # 保存模型
        model_dir = Path("models") / config.model_name
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / "model.joblib"
        joblib.dump(final_model, str(model_path))

        # 保存 metadata
        metadata = {
            "model_name": config.model_name,
            "model_type": "lightgbm",
            "created_at": datetime.now().isoformat(),
            "label_horizon": 5,
            "feature_count": len(feature_cols),
            "train_samples": len(dataset),
            "best_params": best_params,
            "cv_metrics": {"mean_ic": mean_ic, "ic_ir": ic_ir},
            "feature_columns": feature_cols,
        }
        (model_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str))

        # 保存特征重要性 CSV
        fi_df = pd.DataFrame(
            [{"feature": k, "importance": v} for k, v in sorted(importances.items(), key=lambda x: -x[1])]
        )
        fi_df.to_csv(model_dir / "feature_importance.csv", index=False)

        return TrainResult(
            model_name=config.model_name,
            best_params=best_params,
            cv_metrics=cv_metrics,
            mean_ic=mean_ic,
            ic_ir=ic_ir,
            feature_importance=importances,
            model_path=str(model_path),
            train_samples=len(dataset),
            feature_count=len(feature_cols),
        )

    @staticmethod
    def _objective(
        trial,
        dataset: pd.DataFrame,
        folds: list[tuple[pd.Index, pd.Index]],
        feature_cols: list[str],
        label_col: str,
        config: TrainConfig,
    ) -> float:
        """Optuna 目标函数：最大化 CV 平均 IC。"""
        import lightgbm as lgb

        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 2000),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "num_leaves": trial.suggest_int("num_leaves", 15, 255),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        }

        ics: list[float] = []
        for train_idx, test_idx in folds:
            x_train = dataset.loc[train_idx, feature_cols]
            y_train = dataset.loc[train_idx, label_col]
            x_test = dataset.loc[test_idx, feature_cols]
            y_test = dataset.loc[test_idx, label_col]

            model = lgb.LGBMRegressor(
                objective="regression",
                metric="mse",
                verbosity=-1,
                boosting_type="gbdt",
                seed=config.random_seed,
                **params,
            )
            model.fit(
                x_train, y_train,
                eval_set=[(x_test, y_test)],
                callbacks=[lgb.early_stopping(config.early_stopping_rounds, verbose=False)],
            )
            preds = model.predict(x_test)
            ic, _ = spearmanr(preds, y_test)
            if np.isnan(ic):
                ic = 0.0
            ics.append(ic)

        return float(np.mean(ics))
