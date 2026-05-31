"""LightGBM 训练管道 — Walk-Forward + Optuna 超参优化。"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.infrastructure.ml_engine.feature_combiner import AutoFeatureCombiner


@dataclass(slots=True, kw_only=True)
class LGBMConfig:
    """LightGBM 训练配置。"""
    n_estimators: int = 500
    learning_rate: float = 0.05
    max_depth: int = 6
    num_leaves: int = 31
    min_child_samples: int = 50
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.1
    reg_lambda: float = 0.1
    random_state: int = 42
    objective: str = "binary"
    metric: str = "auc"

    def to_lgbm_params(self) -> dict:
        """转换为 LightGBM 参数字典。"""
        return {
            "n_estimators": self.n_estimators,
            "learning_rate": self.learning_rate,
            "max_depth": self.max_depth,
            "num_leaves": self.num_leaves,
            "min_child_samples": self.min_child_samples,
            "subsample": self.subsample,
            "colsample_bytree": self.colsample_bytree,
            "reg_alpha": self.reg_alpha,
            "reg_lambda": self.reg_lambda,
            "random_state": self.random_state,
            "objective": self.objective,
            "metric": self.metric,
            "verbose": -1,
        }


@dataclass(slots=True, kw_only=True)
class WalkForwardResult:
    """Walk-Forward 训练结果。"""
    train_period: tuple[date, date]
    val_period: tuple[date, date]
    test_period: tuple[date, date]
    val_ic: float
    test_ic: float
    feature_importance: dict[str, float]
    model_path: str


class TrainingPipeline:
    """LightGBM 训练管道。"""

    def __init__(self, config: LGBMConfig | None = None) -> None:
        self._config = config or LGBMConfig()
        self._combiner = AutoFeatureCombiner()

    def prepare_dataset(
        self,
        snapshots_by_date: dict[date, list[StockSnapshot]],
        forward_days: int = 20,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """准备训练数据集: 特征矩阵 + 标签。

        Args:
            snapshots_by_date: 按日期索引的快照字典。
            forward_days: 前瞻期天数。

        Returns:
            (features, labels): 特征矩阵, 二分类标签 (1=涨, 0=跌)。
        """
        sorted_dates = sorted(snapshots_by_date.keys())
        if len(sorted_dates) <= forward_days:
            return pd.DataFrame(), pd.Series(dtype=float)

        # 分割日期：特征日期 vs 标签日期
        feature_dates = sorted_dates[:-forward_days]
        label_dates = sorted_dates[forward_days:]

        # 构建特征矩阵
        all_features: list[pd.DataFrame] = []
        all_labels: list[pd.Series] = []

        for feat_date, label_date in zip(feature_dates, label_dates):
            feat_snapshots = snapshots_by_date[feat_date]
            label_snapshots = snapshots_by_date[label_date]

            if not feat_snapshots or not label_snapshots:
                continue

            # 特征
            feat_dt = self._combiner.generate_combinations(feat_snapshots)

            # 标签：用 label_date 的 return_5d 作为前瞻收益代理
            label_map: dict[str, float] = {}
            for s in label_snapshots:
                if s.return_5d is not None:
                    label_map[s.symbol] = s.return_5d

            # 取交集
            common = feat_dt.index.intersection(pd.Index(label_map.keys()))
            if len(common) < 30:
                continue

            feat_dt = feat_dt.loc[common]
            label_dt = pd.Series(
                {sym: 1.0 if label_map[sym] > 0 else 0.0 for sym in common},
                index=common,
            )

            # 添加日期作为多索引的第二级（用于 walk-forward 切分）
            feat_dt.index = pd.MultiIndex.from_arrays(
                [[feat_date] * len(common), feat_dt.index],
                names=["date", "symbol"],
            )
            label_dt.index = feat_dt.index

            all_features.append(feat_dt)
            all_labels.append(label_dt)

        if not all_features:
            return pd.DataFrame(), pd.Series(dtype=float)

        features = pd.concat(all_features)
        labels = pd.concat(all_labels)

        # NaN 处理：中位数填充
        features = features.fillna(features.median())
        # 丢弃仍有 NaN 的行
        mask = features.notna().all(axis=1)
        features = features[mask]
        labels = labels[mask]

        return features, labels

    def train(
        self,
        feat_train: pd.DataFrame,
        label_train: pd.Series,
        feat_val: pd.DataFrame,
        label_val: pd.Series,
        config: LGBMConfig | None = None,
    ) -> object:
        """训练 LightGBM 模型。

        Returns:
            训练好的 LGBMClassifier 实例。
        """
        import lightgbm as lgb

        cfg = config or self._config
        params = cfg.to_lgbm_params()

        model = lgb.LGBMClassifier(**params)
        model.fit(
            feat_train, label_train,
            eval_set=[(feat_val, label_val)],
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )
        return model

    def optimize_hyperparams(
        self,
        feat_train: pd.DataFrame,
        label_train: pd.Series,
        feat_val: pd.DataFrame,
        label_val: pd.Series,
        n_trials: int = 50,
    ) -> LGBMConfig:
        """Optuna 超参数优化。优化目标: 验证集 IC。"""
        import optuna

        def objective(trial: optuna.Trial) -> float:
            config = LGBMConfig(
                n_estimators=trial.suggest_int("n_estimators", 100, 1000),
                learning_rate=trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
                max_depth=trial.suggest_int("max_depth", 3, 8),
                num_leaves=trial.suggest_int("num_leaves", 15, 63),
                min_child_samples=trial.suggest_int("min_child_samples", 20, 200),
                subsample=trial.suggest_float("subsample", 0.6, 1.0),
                colsample_bytree=trial.suggest_float("colsample_bytree", 0.6, 1.0),
                reg_alpha=trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
                reg_lambda=trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            )
            model = self.train(feat_train, label_train, feat_val, label_val, config)
            preds = model.predict_proba(feat_val)[:, 1]
            ic, _ = spearmanr(preds, label_val)
            return abs(ic) if not np.isnan(ic) else 0.0

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=n_trials)
        return LGBMConfig(**study.best_params)

    def walk_forward_train(
        self,
        snapshots_by_date: dict[date, list[StockSnapshot]],
        train_years: int = 3,
        val_months: int = 6,
        test_months: int = 6,
        step_months: int = 6,
        model_dir: str = "data/factors/models",
    ) -> list[WalkForwardResult]:
        """Walk-Forward 滚动训练。"""
        sorted_dates = sorted(snapshots_by_date.keys())
        if not sorted_dates:
            return []

        results: list[WalkForwardResult] = []

        # 计算窗口大小（交易日）
        train_days = train_years * 252
        val_days = val_months * 21
        test_days = test_months * 21
        step_days = step_months * 21

        total_needed = train_days + val_days + test_days
        if len(sorted_dates) < total_needed:
            return []

        Path(model_dir).mkdir(parents=True, exist_ok=True)

        start_idx = 0
        window_idx = 0
        while start_idx + total_needed <= len(sorted_dates):
            train_start = sorted_dates[start_idx]
            train_end = sorted_dates[start_idx + train_days - 1]
            val_start = sorted_dates[start_idx + train_days]
            val_end = sorted_dates[start_idx + train_days + val_days - 1]
            test_start = sorted_dates[start_idx + train_days + val_days]
            test_end_idx = min(start_idx + total_needed - 1, len(sorted_dates) - 1)
            test_end = sorted_dates[test_end_idx]

            # 准备各窗口数据
            train_dates_range = sorted_dates[start_idx:start_idx + train_days]
            val_dates_range = sorted_dates[start_idx + train_days:start_idx + train_days + val_days]
            test_dates_range = sorted_dates[start_idx + train_days + val_days:start_idx + total_needed]

            train_snaps = {d: snapshots_by_date[d] for d in train_dates_range if d in snapshots_by_date}
            val_snaps = {d: snapshots_by_date[d] for d in val_dates_range if d in snapshots_by_date}
            test_snaps = {d: snapshots_by_date[d] for d in test_dates_range if d in snapshots_by_date}

            feat_train, label_train = self.prepare_dataset(train_snaps)
            feat_val, label_val = self.prepare_dataset(val_snaps)
            feat_test, label_test = self.prepare_dataset(test_snaps)

            if feat_train.empty or feat_val.empty:
                start_idx += step_days
                continue

            # 训练
            model = self.train(feat_train, label_train, feat_val, label_val)

            # 评估
            val_preds = model.predict_proba(feat_val)[:, 1]
            val_ic, _ = spearmanr(val_preds, label_val)
            val_ic = float(val_ic) if not np.isnan(val_ic) else 0.0

            test_ic = 0.0
            if not feat_test.empty:
                test_preds = model.predict_proba(feat_test)[:, 1]
                ic, _ = spearmanr(test_preds, label_test)
                test_ic = float(ic) if not np.isnan(ic) else 0.0

            # 特征重要性
            importance: dict[str, float] = {}
            if hasattr(model, "feature_importances_"):
                for fname, imp in zip(feat_train.columns, model.feature_importances_):
                    importance[fname] = float(imp)

            # 保存模型
            model_path = f"{model_dir}/lgbm_wf_{window_idx:03d}.pkl"
            with open(model_path, "wb") as f:
                pickle.dump(model, f)

            results.append(WalkForwardResult(
                train_period=(train_start, train_end),
                val_period=(val_start, val_end),
                test_period=(test_start, test_end),
                val_ic=val_ic,
                test_ic=test_ic,
                feature_importance=importance,
                model_path=model_path,
            ))

            window_idx += 1
            start_idx += step_days

        return results
