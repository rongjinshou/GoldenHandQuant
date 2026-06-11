"""DuckDB 历史数据源 — 回测直接消费 market.duckdb 前复权日线。

与因子研究共库（同一份数据口径），QMT 不在线也能跑全市场回测；
库内缺失的标的（如指数）可回退既有 fetcher。
设计: docs/feat/0611-backtest-duckdb/2026-06-11-backtest-duckdb-design.md
"""

from __future__ import annotations

import logging
from datetime import datetime

import duckdb

from src.domain.market.interfaces.gateways.history_fetcher import IHistoryDataFetcher
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe

logger = logging.getLogger(__name__)


class DuckDBHistoryDataFetcher(IHistoryDataFetcher):
    """从 market.duckdb 读前复权日线。

    持单条 read_only 连接（全市场回测逐 symbol 开连接代价过高）；
    read_only 与其他读者共存、与写进程（refresh/factor-test）互斥——
    回测期间勿跑刷数任务。
    """

    def __init__(self, db_path: str = "data/market.duckdb",
                 fallback: IHistoryDataFetcher | None = None) -> None:
        self._conn = duckdb.connect(db_path, read_only=True)
        self._fallback = fallback

    def close(self) -> None:
        self._conn.close()

    def fetch_history_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_date: str,
        end_date: str,
    ) -> list[Bar]:
        if timeframe != Timeframe.DAY_1:
            return self._fall_back(symbol, timeframe, start_date, end_date,
                                   reason=f"库仅日线, 请求 {timeframe.value}")

        rows = self._conn.execute(
            """SELECT date, open, high, low, close, volume, prev_close
               FROM bars WHERE symbol = ? AND date BETWEEN ? AND ?
               ORDER BY date""",
            [symbol, start_date, end_date],
        ).fetchall()

        if not rows:
            return self._fall_back(symbol, timeframe, start_date, end_date,
                                   reason="库内无该标的区间数据")

        return [
            Bar(
                symbol=symbol,
                timeframe=Timeframe.DAY_1,
                timestamp=datetime.combine(row[0], datetime.min.time()),
                open=row[1], high=row[2], low=row[3], close=row[4],
                volume=row[5], prev_close=row[6],
            )
            for row in rows
        ]

    def _fall_back(self, symbol: str, timeframe: Timeframe,
                   start_date: str, end_date: str, *, reason: str) -> list[Bar]:
        if self._fallback is None:
            logger.warning("DuckDB 数据源缺数且无回退: %s (%s)", symbol, reason)
            return []
        logger.info("DuckDB 数据源回退 %s: %s", symbol, reason)
        return self._fallback.fetch_history_bars(symbol, timeframe, start_date, end_date)
