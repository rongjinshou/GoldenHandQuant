"""投研只读端点 — 数据资产/因子判决/标的搜索/K线/特征曲线。

仅消费本地 market.duckdb（read_only 连接，不与 factor-test 等写进程抢锁）；
不调 QMT、不做写操作。鉴权边界见设计文档 D4（仅绑 127.0.0.1）。
设计: docs/feat/0611-dashboard/2026-06-11-research-dashboard-design.md §4
"""

from __future__ import annotations

import math
import os
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from src.domain.market.services.feature_engine import FEATURE_VERSION, TECHNICAL_COLUMNS
from src.infrastructure.persistence.market_data_store import MarketDataStore

router = APIRouter()

_EMPTY_TABLES = {
    t: {"rows": 0, "symbols": 0, "min_date": None, "max_date": None}
    for t in ("instruments", "bars", "fundamental_snapshots", "stock_features")
}


def _db_path() -> str:
    return os.environ.get("GHQ_MARKET_DB", "data/market.duckdb")


def get_research_store() -> Iterator[MarketDataStore | None]:
    """每请求一个只读连接；库文件不存在时给 None（端点返回空态）。"""
    path = _db_path()
    if not Path(path).exists():
        yield None
        return
    store = MarketDataStore(path, read_only=True)
    try:
        yield store
    finally:
        store.close()


def _nn(value: float | None) -> float | None:
    """NaN → None，保证 JSON 合法。"""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value


@router.get("/overview")
async def overview(store: MarketDataStore | None = Depends(get_research_store)):
    if store is None:
        return {"db_exists": False, "db_path": _db_path(),
                "feature_version": FEATURE_VERSION, "tables": _EMPTY_TABLES,
                "verdict_runs": 0}
    return {
        "db_exists": True,
        "db_path": _db_path(),
        "feature_version": FEATURE_VERSION,
        "tables": store.table_stats(),
        "verdict_runs": len(store.load_verdict_runs()),
    }


@router.get("/verdicts")
async def verdicts(store: MarketDataStore | None = Depends(get_research_store)):
    if store is None:
        return {"runs": []}
    return {"runs": store.load_verdict_runs()}


@router.get("/symbols")
async def symbols(
    q: str = "",
    limit: int = 50,
    store: MarketDataStore | None = Depends(get_research_store),
):
    if store is None or not q:
        return []
    return store.search_instruments(q, limit=min(limit, 200))


@router.get("/bars/{symbol}")
async def bars(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    source: str = "qmt",
    store: MarketDataStore | None = Depends(get_research_store),
):
    start, end = _default_range(start, end)
    if store is None:
        return {"dates": [], "ohlc": [], "volume": []}
    df = store.load_bars_df([symbol], start, end, source)
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in df["date"]],
        # ECharts candlestick 约定 [open, close, low, high]
        "ohlc": [
            [_nn(o), _nn(c), _nn(lo), _nn(h)]
            for o, c, lo, h in zip(df["open"], df["close"], df["low"], df["high"],
                                   strict=True)
        ],
        "volume": [_nn(v) for v in df["volume"]],
    }


@router.get("/features/{symbol}")
async def features(
    symbol: str,
    names: str = "return_20d,volatility_20d",
    start: str | None = None,
    end: str | None = None,
    store: MarketDataStore | None = Depends(get_research_store),
):
    requested = [n.strip() for n in names.split(",") if n.strip()]
    unknown = [n for n in requested if n not in TECHNICAL_COLUMNS]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"未知特征名: {unknown}; 可选: {list(TECHNICAL_COLUMNS)}",
        )
    start, end = _default_range(start, end)
    if store is None:
        return {"dates": [], "series": {n: [] for n in requested}}
    df = store.load_features_df([symbol], start, end, FEATURE_VERSION)
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in df["date"]],
        "series": {n: [_nn(v) for v in df[n]] for n in requested},
    }


def _default_range(start: str | None, end: str | None) -> tuple[str, str]:
    """默认近一年。"""
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    if start is None:
        start = (datetime.strptime(end, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
    return start, end
