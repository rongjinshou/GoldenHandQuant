"""LightGBM 训练管道 — Walk-Forward + Optuna 超参优化。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.infrastructure.ml_engine.feature_transforms import (
    compute_derived_features,
    cross_section_standardize,
    extract_base_features,
)
from src.infrastructure.ml_engine.label_generator import LabelConfig, generate_labels


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

        # 构建特征矩阵（使用 extract_base_features + compute_derived_features）
        # 同时构建 price_series 供 label_generator 使用
        price_series: dict[str, dict[date, float]] = {}
        all_rows: list[dict[str, float | None]] = []

        for d in sorted_dates:
            snapshots = snapshots_by_date[d]
            if not snapshots:
                continue

            rows = [extract_base_features(s) for s in snapshots]
            for row, snap in zip(rows, snapshots):
                row["close"] = snap.close
                # 收集价格序列
                if snap.symbol not in price_series:
                    price_series[snap.symbol] = {}
                price_series[snap.symbol][d] = snap.close

            compute_derived_features(rows)
            all_rows.extend(rows)

        if not all_rows:
            return pd.DataFrame(), pd.Series(dtype=float)

        df = pd.DataFrame(all_rows)

        # 确定特征列（排除非特征列）
        exclude_cols = {"date", "symbol", "label", "close"}
        feature_cols = [
            c for c in df.columns
            if c not in exclude_cols and df[c].dtype in ("float64", "float32", "int64")
        ]

        # 截面标准化
        cross_section_standardize(df, feature_cols)

        # 使用 label_generator 生成前瞻收益标签
        price_series_pd: dict[str, pd.Series] = {
            sym: pd.Series(prices) for sym, prices in price_series.items()
        }
        label_config = LabelConfig(
            horizon=forward_days,
            label_type="fwd_return",
            winsorize_quantile=0.01,
        )
        df["label"] = generate_labels(df, price_series_pd, label_config)

        # 丢弃 label 为 NaN 的行
        df = df.dropna(subset=["label"]).reset_index(drop=True)
        if df.empty:
            return pd.DataFrame(), pd.Series(dtype=float)

        # 二分类标签：1=涨, 0=跌
        labels = (df["label"] > 0).astype(float)

        # 构建特征矩阵
        features = df[feature_cols].copy()

        # 注意：不在这里做 fillna，避免测试集数据参与训练集的中位数计算。
        # NaN 处理由调用方（walk_forward_train）基于训练集统计量完成。

        # 添加日期-标的多索引（用于 walk-forward 切分）
        dates = df.loc[features.index, "date"]
        symbols = df.loc[features.index, "symbol"]
        multi_idx = pd.MultiIndex.from_arrays(
            [dates.values, symbols.values],
            names=["date", "symbol"],
        )
        features.index = multi_idx
        labels.index = multi_idx

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
        forward_days: int = 20,
    ) -> list[WalkForwardResult]:
        """Walk-Forward 滚动训练。

        Args:
            forward_days: 前瞻期天数，同时用作 train/val、val/test 之间的 embargo 窗口。
        """
        sorted_dates = sorted(snapshots_by_date.keys())
        if not sorted_dates:
            return []

        results: list[WalkForwardResult] = []

        # 计算窗口大小（交易日）
        train_days = train_years * 252
        val_days = val_months * 21
        test_days = test_months * 21
        step_days = step_months * 21
        embargo_days = forward_days  # embargo 窗口 = 前瞻期天数

        total_needed = train_days + embargo_days + val_days + embargo_days + test_days
        if len(sorted_dates) < total_needed:
            return []

        Path(model_dir).mkdir(parents=True, exist_ok=True)

        start_idx = 0
        window_idx = 0
        while start_idx + total_needed <= len(sorted_dates):
            train_start = sorted_dates[start_idx]
            train_end = sorted_dates[start_idx + train_days - 1]

            # embargo gap between train and val
            val_start_idx = start_idx + train_days + embargo_days
            val_start = sorted_dates[val_start_idx]
            val_end = sorted_dates[val_start_idx + val_days - 1]

            # embargo gap between val and test
            test_start_idx = val_start_idx + val_days + embargo_days
            test_start = sorted_dates[test_start_idx]
            test_end_idx = min(start_idx + total_needed - 1, len(sorted_dates) - 1)
            test_end = sorted_dates[test_end_idx]

            # 准备各窗口数据
            train_dates_range = sorted_dates[start_idx:start_idx + train_days]
            val_dates_range = sorted_dates[val_start_idx:val_start_idx + val_days]
            test_dates_range = sorted_dates[test_start_idx:start_idx + total_needed]

            train_snaps = {d: snapshots_by_date[d] for d in train_dates_range if d in snapshots_by_date}
            val_snaps = {d: snapshots_by_date[d] for d in val_dates_range if d in snapshots_by_date}
            test_snaps = {d: snapshots_by_date[d] for d in test_dates_range if d in snapshots_by_date}

            feat_train, label_train = self.prepare_dataset(train_snaps, forward_days=forward_days)
            feat_val, label_val = self.prepare_dataset(val_snaps, forward_days=forward_days)
            feat_test, label_test = self.prepare_dataset(test_snaps, forward_days=forward_days)

            if feat_train.empty or feat_val.empty:
                start_idx += step_days
                continue

            # Issue #1 (NEW-H5): fillna 只用训练集的中位数，避免测试集信息泄露
            train_medians = feat_train.median()
            feat_train = feat_train.fillna(train_medians)
            feat_val = feat_val.fillna(train_medians)
            feat_test = feat_test.fillna(train_medians)

            # 丢弃训练集中仍有 NaN 的行
            train_mask = feat_train.notna().all(axis=1)
            feat_train = feat_train[train_mask]
            label_train = label_train[train_mask]

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

            # 保存模型（joblib 格式，路径与 model_loader.py 的 load_lightgbm 一致：models/{name}/model.joblib）
            model_name = f"lgbm_wf_{window_idx:03d}"
            fold_model_dir = Path(model_dir) / model_name
            fold_model_dir.mkdir(parents=True, exist_ok=True)
            model_path = str(fold_model_dir / "model.joblib")
            joblib.dump(model, model_path)

            # 保存 metadata（含 feature_columns）
            metadata = {
                "model_name": f"lgbm_wf_{window_idx:03d}",
                "model_type": "lightgbm",
                "feature_columns": list(feat_train.columns),
                "feature_count": len(feat_train.columns),
                "train_period": (train_start.isoformat(), train_end.isoformat()),
                "val_period": (val_start.isoformat(), val_end.isoformat()),
                "test_period": (test_start.isoformat(), test_end.isoformat()),
                "val_ic": val_ic,
                "test_ic": test_ic,
                "embargo_days": embargo_days,
            }
            metadata_path = str(fold_model_dir / "metadata.json")
            Path(metadata_path).write_text(json.dumps(metadata, indent=2, default=str))

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
