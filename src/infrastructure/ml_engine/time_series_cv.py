"""时间序列交叉验证：Purged Walk-Forward CV。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True, kw_only=True)
class TimeSeriesCVConfig:
    """时间序列交叉验证配置。"""
    n_splits: int = 5
    test_size_months: int = 6
    gap_days: int = 5
    min_train_days: int = 500
    max_train_size: int | None = None


class PurgedWalkForwardCV:
    """Purged Walk-Forward 交叉验证器。

    训练集为扩展窗口（Expanding Window），测试集为滚动窗口。
    Gap 窗口防止标签重叠泄露。
    """

    def __init__(self, config: TimeSeriesCVConfig) -> None:
        self._config = config

    def split(
        self, df: pd.DataFrame
    ) -> list[tuple[pd.Index, pd.Index]]:
        """生成 (train_idx, test_idx) 对。

        Args:
            df: 包含 'date' 列的数据集。

        Returns:
            list of (train_index, test_index)。
        """
        dates = sorted(df["date"].unique())
        n_dates = len(dates)
        if n_dates < self._config.min_train_days + self._config.gap_days + 1:
            return []

        test_days = self._config.test_size_months * 21  # 约每月 21 个交易日
        gap = self._config.gap_days
        min_train = self._config.min_train_days

        folds: list[tuple[pd.Index, pd.Index]] = []

        # 从后往前确定测试窗口的起始位置
        test_end = n_dates
        while test_end > min_train + gap + test_days and len(folds) < self._config.n_splits:
            test_start = test_end - test_days
            train_end = test_start - gap

            if train_end < min_train:
                break

            train_start = 0
            if self._config.max_train_size is not None and train_end - train_start > self._config.max_train_size:
                train_start = train_end - self._config.max_train_size

            train_dates = dates[train_start:train_end]
            test_dates = dates[test_start:test_end]

            train_mask = df["date"].isin(set(train_dates))
            test_mask = df["date"].isin(set(test_dates))

            train_idx = df.index[train_mask]
            test_idx = df.index[test_mask]

            if len(train_idx) > 0 and len(test_idx) > 0:
                folds.append((train_idx, test_idx))

            # 滚动：下折的测试窗口往前推进 test_days
            test_end = test_start

        # 返回时按时间正序（最早的折在前）
        folds.reverse()
        # 只取最后 n_splits 折
        if len(folds) > self._config.n_splits:
            folds = folds[-self._config.n_splits:]

        return folds


def validate_no_leakage(
    df: pd.DataFrame,
    train_idx: pd.Index,
    test_idx: pd.Index,
    label_col: str = "label",
    gap_days: int = 5,
) -> bool:
    """检查训练集和测试集之间是否存在时间泄露。

    Returns:
        True 表示无泄露。
    """
    train_dates = df.loc[train_idx, "date"]
    test_dates = df.loc[test_idx, "date"]

    if train_dates.empty or test_dates.empty:
        return True

    train_max = train_dates.max()
    test_min = test_dates.min()

    # Gap 检查：训练集最大日期 + gap 应 <= 测试集最小日期
    # 使用日期排序来近似 gap
    all_dates = sorted(df["date"].unique())
    train_max_idx = next(i for i, d in enumerate(all_dates) if d == train_max)
    required_idx = train_max_idx + gap_days
    if required_idx < len(all_dates) and all_dates[required_idx] > test_min:
        return False

    return True
