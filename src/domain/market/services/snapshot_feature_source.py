"""截面快照的技术特征源 — 统一到 feature_engine(纠错版), 替代 CrossSectionBuilder 手写重算。

B7: 回测 runner 原走 `CrossSectionBuilder._compute_bar_metrics`(手写, return_20d 口径 bug);
本源改用 `feature_engine`(stock_features 的同一向量化引擎), 使回测与因子检验指标口径统一。
喂完整窗口(info_bars + exec_bar, 末根=T), 取末行技术列(feature_engine 内部 shift(1) → as-of-T-1),
正是快照(T-1 信息)语义。domain 红线允许 pandas 纯计算。
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

import pandas as pd

from src.domain.market.services.feature_engine import (
    TECHNICAL_COLUMNS,
    compute_symbol_features,
)
from src.domain.market.value_objects.bar import Bar


class FeatureEngineSnapshotSource:
    """用 feature_engine 从单只完整 bar 窗口算出快照技术特征。"""

    def features_for(self, symbol: str, window_bars: list[Bar]) -> dict[str, float]:
        """返回 {技术指标: 值}(NaN 略去)。window_bars 升序, 末根 = 成交日 T。"""
        if len(window_bars) < 2:
            return {}
        df = pd.DataFrame({
            "symbol": [symbol] * len(window_bars),
            "date": [b.timestamp for b in window_bars],
            "open": [b.open for b in window_bars],
            "high": [b.high for b in window_bars],
            "low": [b.low for b in window_bars],
            "close": [b.close for b in window_bars],
            "volume": [b.volume for b in window_bars],
            "prev_close": [b.prev_close for b in window_bars],
        })
        feats = compute_symbol_features(df)
        if feats.empty:
            return {}
        last = feats.iloc[-1]
        out: dict[str, float] = {}
        for col in TECHNICAL_COLUMNS:
            val = last[col]
            if pd.notna(val):
                out[col] = float(val)
        return out


class IBacktestFeatureSource(Protocol):
    """回测/实盘 runner 的截面技术特征源。"""

    def features_for(
        self, date: datetime, symbols: list[str], windows: dict[str, list[Bar]]
    ) -> dict[str, dict[str, float]]:
        """返回 {symbol: {技术指标: 值}}（当日 T 的快照特征, as-of T-1）。"""
        ...


class FeatureEngineFeatureSource:
    """当场用 feature_engine 算（实盘/无库回退；逐股向量化, 口径=stock_features）。"""

    def __init__(self) -> None:
        self._src = FeatureEngineSnapshotSource()

    def features_for(
        self, date: datetime, symbols: list[str], windows: dict[str, list[Bar]]
    ) -> dict[str, dict[str, float]]:
        return {
            sym: self._src.features_for(sym, windows[sym])
            for sym in symbols if sym in windows
        }


class StoredFeatureSource:
    """读已入库 stock_features（离线回测复用别重算）。

    features_df: 列含 date / symbol / 各 TECHNICAL_COLUMNS。按日预分组, 每日按需转 dict。
    """

    def __init__(self, features_df: pd.DataFrame) -> None:
        self._cols = [c for c in TECHNICAL_COLUMNS if c in features_df.columns]
        self._by_date: dict[str, pd.DataFrame] = {}
        if not features_df.empty:
            ds = pd.to_datetime(features_df["date"]).dt.strftime("%Y-%m-%d")
            for key, grp in features_df.groupby(ds, sort=False):
                self._by_date[key] = grp

    def features_for(
        self, date: datetime, symbols: list[str], windows: dict[str, list[Bar]]
    ) -> dict[str, dict[str, float]]:
        day = self._by_date.get(pd.Timestamp(date).strftime("%Y-%m-%d"))
        if day is None:
            return {}
        wanted = set(symbols)
        out: dict[str, dict[str, float]] = {}
        for row in day.itertuples(index=False):
            sym = row.symbol
            if sym not in wanted:
                continue
            feats = {
                c: float(getattr(row, c))
                for c in self._cols
                if pd.notna(getattr(row, c))
            }
            out[sym] = feats
        return out
