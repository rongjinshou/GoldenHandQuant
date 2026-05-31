"""测试时间序列交叉验证。"""

import pandas as pd

from src.infrastructure.ml_engine.time_series_cv import (
    PurgedWalkForwardCV,
    TimeSeriesCVConfig,
    validate_no_leakage,
)


def _make_df(n_dates: int = 600, n_symbols: int = 5) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=n_dates)
    rows = []
    for d in dates:
        for s in range(n_symbols):
            rows.append({"date": d, "symbol": f"S{s}", "f1": 0.0, "label": 0.0})
    return pd.DataFrame(rows)


class TestPurgedWalkForwardCV:
    def test_basic_split(self) -> None:
        df = _make_df(700, 3)
        config = TimeSeriesCVConfig(n_splits=3, test_size_months=3, gap_days=5, min_train_days=200)
        cv = PurgedWalkForwardCV(config)
        folds = cv.split(df)
        assert len(folds) > 0
        assert len(folds) <= 3

    def test_train_before_test(self) -> None:
        df = _make_df(700, 3)
        config = TimeSeriesCVConfig(n_splits=3, test_size_months=3, gap_days=5, min_train_days=200)
        cv = PurgedWalkForwardCV(config)
        folds = cv.split(df)

        for train_idx, test_idx in folds:
            train_dates = df.loc[train_idx, "date"]
            test_dates = df.loc[test_idx, "date"]
            assert train_dates.max() < test_dates.min()

    def test_expanding_train_window(self) -> None:
        df = _make_df(800, 3)
        config = TimeSeriesCVConfig(n_splits=3, test_size_months=3, gap_days=5, min_train_days=200)
        cv = PurgedWalkForwardCV(config)
        folds = cv.split(df)

        if len(folds) >= 2:
            for i in range(1, len(folds)):
                prev_train_len = len(folds[i - 1][0])
                curr_train_len = len(folds[i][0])
                assert curr_train_len >= prev_train_len

    def test_insufficient_data_returns_empty(self) -> None:
        df = _make_df(100, 3)
        config = TimeSeriesCVConfig(n_splits=5, test_size_months=6, gap_days=5, min_train_days=500)
        cv = PurgedWalkForwardCV(config)
        folds = cv.split(df)
        assert len(folds) == 0

    def test_gap_separates_train_and_test(self) -> None:
        df = _make_df(700, 3)
        config = TimeSeriesCVConfig(n_splits=3, test_size_months=3, gap_days=10, min_train_days=200)
        cv = PurgedWalkForwardCV(config)
        folds = cv.split(df)

        all_dates = sorted(df["date"].unique())
        for train_idx, test_idx in folds:
            train_max = df.loc[train_idx, "date"].max()
            test_min = df.loc[test_idx, "date"].min()
            train_max_pos = list(all_dates).index(train_max)
            test_min_pos = list(all_dates).index(test_min)
            # gap >= gap_days
            assert test_min_pos - train_max_pos >= config.gap_days


class TestValidateNoLeakage:
    def test_no_leakage_passes(self) -> None:
        df = _make_df(300, 3)
        dates = sorted(df["date"].unique())
        train_dates = set(dates[:200])
        test_dates = set(dates[210:])
        train_idx = df[df["date"].isin(train_dates)].index
        test_idx = df[df["date"].isin(test_dates)].index
        assert validate_no_leakage(df, train_idx, test_idx, gap_days=5) is True

    def test_insufficient_gap_fails(self) -> None:
        df = _make_df(300, 3)
        dates = sorted(df["date"].unique())
        train_dates = set(dates[:200])
        test_dates = set(dates[201:210])  # 仅 1 天 gap
        train_idx = df[df["date"].isin(train_dates)].index
        test_idx = df[df["date"].isin(test_dates)].index
        assert validate_no_leakage(df, train_idx, test_idx, gap_days=5) is False
