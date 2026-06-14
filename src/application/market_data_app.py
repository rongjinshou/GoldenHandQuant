"""市场数据应用服务 — 缺口刷新编排 + 截面装载（DB 快路径）。

职责（设计 §7）:
1. ensure_*: 对照 fetch_meta 履约区间，只拉缺口 → upsert → 更新履约
2. ensure_features: bars 有变化或特征区间有缺口的 symbol 整只重算（向量化）
3. load_cross_sections: features ⋈ fundamentals → 与旧 prepare_snapshots
   完全同构的三个 dict，FactorTestRunner 零改动

设计文档: docs/feat/0611-market-data-store/2026-06-11-market-data-store-design.md
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.domain.market.services.feature_engine import (
    FEATURE_VERSION,
    TECHNICAL_COLUMNS,
    WARMUP_DAYS,
    compute_features,
)
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.factor_test.panel import FactorPanel

if TYPE_CHECKING:
    from src.domain.market.interfaces.gateways.fundamental_fetcher import IFundamentalFetcher
    from src.domain.market.interfaces.gateways.history_fetcher import IHistoryDataFetcher
    from src.infrastructure.persistence.market_data_store import MarketDataStore

_SYMBOL_CHUNK = 500  # 特征重算/批量装载的分块大小


def _warmup_start(start_date: str) -> str:
    return (
        datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=WARMUP_DAYS)
    ).strftime("%Y-%m-%d")


def _nn(value: float | None) -> float | None:
    """NaN → None（StockSnapshot 可选字段约定）。"""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value


class MarketDataAppService:
    """市场数据编排服务。日期参数统一 'YYYY-MM-DD' 字符串。"""

    def __init__(
        self,
        store: MarketDataStore,
        history_fetcher: IHistoryDataFetcher,
        fundamental_fetcher: IFundamentalFetcher,
        source: str = "qmt",
    ) -> None:
        self._store = store
        self._history_fetcher = history_fetcher
        self._fundamental_fetcher = fundamental_fetcher
        self._source = source
        self._feature_table = f"stock_features:v{FEATURE_VERSION}"

    # ------------------------------------------------------------------ #
    # ensure（只拉缺口）
    # ------------------------------------------------------------------ #

    def ensure_bars(self, symbols: list[str], start_date: str, end_date: str) -> set[str]:
        """补齐 [start-warmup, end] 的日线缺口。返回本次实际取过数的 symbol 集。"""
        ws = _warmup_start(start_date)
        refreshed: set[str] = set()
        for symbol in symbols:
            gaps = self._store.missing_ranges(self._source, "bars", symbol, ws, end_date)
            if not gaps:
                continue
            for gap_start, gap_end in gaps:
                bars = self._history_fetcher.fetch_history_bars(
                    symbol, Timeframe.DAY_1, gap_start, gap_end
                )
                if bars:
                    self._store.upsert_bars(bars, self._source)
            # 无数据也记履约（未上市/退市区间），防重拉风暴 — 与 csv meta 同口径
            self._store.mark_fulfilled(self._source, "bars", symbol, ws, end_date)
            refreshed.add(symbol)
        return refreshed

    def ensure_fundamentals(self, start_date: str, end_date: str) -> None:
        """补齐基本面缺口（QMT 为整批接口，meta 以 '*' 记一行）。"""
        ws = _warmup_start(start_date)
        gaps = self._store.missing_ranges(
            self._source, "fundamental_snapshots", "*", ws, end_date
        )
        for gap_start, gap_end in gaps:
            snaps = self._fundamental_fetcher.fetch_by_range(gap_start, gap_end)
            if snaps:
                self._store.upsert_fundamentals(snaps, self._source)
        if gaps:
            self._store.mark_fulfilled(
                self._source, "fundamental_snapshots", "*", ws, end_date
            )

    def ensure_features(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        bars_refreshed: set[str] | None = None,
    ) -> int:
        """重算需要更新的 symbol 特征（整只重算，向量化毫秒级）。

        触发条件: 本次取过 bars（数据变了）或特征履约区间有缺口。
        返回重算的 symbol 数。
        """
        bars_refreshed = bars_refreshed or set()
        ws = _warmup_start(start_date)
        stale = [
            s for s in symbols
            if s in bars_refreshed
            or self._store.missing_ranges(self._source, self._feature_table, s, start_date, end_date)
        ]
        for i in range(0, len(stale), _SYMBOL_CHUNK):
            chunk = stale[i: i + _SYMBOL_CHUNK]
            bars_df = self._store.load_bars_df(chunk, ws, end_date, self._source)
            features = compute_features(bars_df)
            self._store.upsert_features_df(features, FEATURE_VERSION)
            for s in chunk:
                self._store.mark_fulfilled(
                    self._source, self._feature_table, s, start_date, end_date
                )
        return len(stale)

    # ------------------------------------------------------------------ #
    # 装载（与旧 prepare_snapshots 同构输出）
    # ------------------------------------------------------------------ #

    def load_cross_sections(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> tuple[
        dict[str, list[StockSnapshot]],
        dict[str, dict[str, float]],
        dict[str, dict[str, float]],
    ]:
        snapshots_by_date: dict[str, list[StockSnapshot]] = {}
        prices_by_date: dict[str, dict[str, float]] = {}

        for i in range(0, len(symbols), _SYMBOL_CHUNK):
            chunk = symbols[i: i + _SYMBOL_CHUNK]
            df = self._store.load_feature_join_df(
                chunk, start_date, end_date, FEATURE_VERSION, self._source
            )
            if df.empty:
                continue
            for row in df.itertuples(index=False):
                ts = row.date.to_pydatetime()
                date_str = ts.strftime("%Y-%m-%d")
                snapshot = StockSnapshot(
                    symbol=row.symbol,
                    date=ts,
                    open=row.open, high=row.high, low=row.low,
                    close=row.close, volume=row.volume,
                    name=row.name,
                    list_date=row.list_date.to_pydatetime(),
                    market_cap=row.market_cap,
                    roe_ttm=_nn(row.roe_ttm), ocf_ttm=_nn(row.ocf_ttm),
                    pe_ratio=_nn(row.pe_ratio), pb_ratio=_nn(row.pb_ratio),
                    earnings_growth=_nn(row.earnings_growth),
                    revenue_growth=_nn(row.revenue_growth),
                    # 旧管道约定: prev_close<=0 视为缺失
                    prev_close=(pc if (pc := _nn(row.prev_close)) and pc > 0 else None),
                    **{name: _nn(getattr(row, name)) for name in TECHNICAL_COLUMNS},
                )
                snapshots_by_date.setdefault(date_str, []).append(snapshot)
                prices_by_date.setdefault(date_str, {})[row.symbol] = row.exec_close

        from src.application.factor_test_app import _compute_forward_returns
        returns_by_date = _compute_forward_returns(prices_by_date)
        return snapshots_by_date, returns_by_date, prices_by_date

    def load_panel(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> FactorPanel:
        """ensure 三连 + 列式装载（向量化路径入口，不物化 StockSnapshot）。

        与 load_cross_sections 同数据源(load_feature_join_df), 但拼成一张列式
        DataFrame 包进 FactorPanel, 供向量化引擎直接 groupby 运算。
        """
        import pandas as pd

        refreshed = self.ensure_bars(symbols, start_date, end_date)
        self.ensure_fundamentals(start_date, end_date)
        recomputed = self.ensure_features(symbols, start_date, end_date, refreshed)
        if refreshed or recomputed:
            print(f"  [market-data] bars 刷新 {len(refreshed)} 只, 特征重算 {recomputed} 只")

        frames: list[pd.DataFrame] = []
        for i in range(0, len(symbols), _SYMBOL_CHUNK):
            chunk = symbols[i: i + _SYMBOL_CHUNK]
            df = self._store.load_feature_join_df(
                chunk, start_date, end_date, FEATURE_VERSION, self._source
            )
            if not df.empty:
                frames.append(df)
        panel_df = (
            pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        )
        return FactorPanel(panel_df)

    def prepare(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> tuple[
        dict[str, list[StockSnapshot]],
        dict[str, dict[str, float]],
        dict[str, dict[str, float]],
    ]:
        """ensure 三连 + 装载（factor-test 的 DB 快路径入口）。"""
        refreshed = self.ensure_bars(symbols, start_date, end_date)
        self.ensure_fundamentals(start_date, end_date)
        recomputed = self.ensure_features(symbols, start_date, end_date, refreshed)
        if refreshed or recomputed:
            print(f"  [market-data] bars 刷新 {len(refreshed)} 只, 特征重算 {recomputed} 只")
        return self.load_cross_sections(symbols, start_date, end_date)
