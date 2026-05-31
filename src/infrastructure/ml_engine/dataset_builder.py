"""从行情数据构建 ML 训练数据集。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from src.infrastructure.ml_engine.feature_transforms import (
    compute_derived_features,
    cross_section_standardize,
    extract_base_features,
)
from src.infrastructure.ml_engine.label_generator import LabelConfig, generate_labels


@dataclass(slots=True, kw_only=True)
class DatasetConfig:
    """数据集构建配置。"""
    label_horizon: int = 5
    label_type: str = "fwd_return"
    winsorize_quantile: float = 0.01
    cross_section_standardize: bool = True
    min_history_days: int = 60
    extra_features: list[str] = field(default_factory=list)


class DatasetBuilder:
    """从行情数据构建 ML 训练数据集。"""

    def __init__(
        self,
        config: DatasetConfig,
    ) -> None:
        self._config = config

    def build(
        self,
        snapshots_by_date: dict[datetime, list],
        price_series: dict[str, pd.Series],
    ) -> pd.DataFrame:
        """构建训练数据集。

        Args:
            snapshots_by_date: {date: [StockSnapshot, ...]}。
            price_series: {symbol: Series(index=date, values=close)} 用于标签生成。

        Returns:
            DataFrame, columns=[date, symbol, feature_1, ..., feature_n, label]
        """
        all_rows: list[dict[str, float | None]] = []

        for date in sorted(snapshots_by_date.keys()):
            snapshots = snapshots_by_date[date]
            rows = [extract_base_features(s) for s in snapshots]

            # 补充 close 字段（StockSnapshot 没有直接暴露 close 到 extract_base_features）
            for row, snap in zip(rows, snapshots):
                row["close"] = snap.close

            compute_derived_features(rows)
            all_rows.extend(rows)

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)

        # 确定特征列
        exclude_cols = {"date", "symbol", "label", "close"}
        feature_cols = [
            c for c in df.columns
            if c not in exclude_cols and df[c].dtype in ("float64", "float32", "int64")
        ]

        # 截面标准化
        if self._config.cross_section_standardize:
            cross_section_standardize(df, feature_cols)

        # 标签生成
        label_config = LabelConfig(
            horizon=self._config.label_horizon,
            label_type=self._config.label_type,
            winsorize_quantile=self._config.winsorize_quantile,
        )
        df["label"] = generate_labels(df, price_series, label_config)

        # 丢弃 label 为 NaN 的行
        df = df.dropna(subset=["label"]).reset_index(drop=True)

        return df

    @staticmethod
    def save(df: pd.DataFrame, path: str) -> None:
        """保存为 parquet。"""
        df.to_parquet(path, index=False)

    @staticmethod
    def load(path: str) -> pd.DataFrame:
        """从 parquet 加载。"""
        return pd.read_parquet(path)
