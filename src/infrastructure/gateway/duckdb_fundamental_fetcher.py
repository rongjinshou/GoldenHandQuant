"""DuckDB 基本面数据源 — 回测离线消费 market.duckdb 的 fundamental_snapshots。

QmtFundamentalFetcher 的离线对偶: 列与 FundamentalSnapshot VO 1:1 映射, 无需 QMT 在线。
market_cap<=0 的行(QMT TotalVolume 缺失造成的数据空洞, ~14%)在 SQL 层剔除——
无有效市值的快照无法参与 size 截面排序(设计 DD-7)。
设计: docs/feat/0613-f01-investability/2026-06-13-f01-investability-design.md
"""

from __future__ import annotations

import logging
from datetime import datetime

import duckdb

from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot

logger = logging.getLogger(__name__)

_COLUMNS = (
    "symbol", "date", "name", "list_date", "market_cap",
    "roe_ttm", "ocf_ttm", "pe_ratio", "pb_ratio",
    "earnings_growth", "revenue_growth",
)


class DuckDBFundamentalFetcher:
    """从 market.duckdb 的 fundamental_snapshots 读基本面快照(read_only)。

    实现 IFundamentalFetcher.fetch_by_range（鸭子类型, 含 QMT 风格 symbols 可选参）。
    与写进程(refresh/factor-test)互斥——回测期间勿跑刷数任务。
    """

    def __init__(self, db_path: str = "data/market.duckdb") -> None:
        self._conn = duckdb.connect(db_path, read_only=True)

    def close(self) -> None:
        self._conn.close()

    def fetch_by_range(
        self, start_date: str, end_date: str, symbols: list[str] | None = None
    ) -> list[FundamentalSnapshot]:
        cols = ", ".join(_COLUMNS)
        sql = (
            f"SELECT {cols} FROM fundamental_snapshots "
            "WHERE date BETWEEN ? AND ? AND market_cap > 0"
        )
        params: list = [start_date, end_date]
        if symbols:
            sql += f" AND symbol IN ({', '.join('?' * len(symbols))})"
            params.extend(symbols)
        sql += " ORDER BY date, symbol"
        try:
            rows = self._conn.execute(sql, params).fetchall()
        except duckdb.Error as e:
            logger.warning("DuckDB 基本面读取失败(%s); 返回空。", e)
            return []
        return [self._to_snapshot(r) for r in rows]

    @staticmethod
    def _to_snapshot(row: tuple) -> FundamentalSnapshot:
        (symbol, date, name, list_date, market_cap, roe_ttm, ocf_ttm,
         pe_ratio, pb_ratio, earnings_growth, revenue_growth) = row
        return FundamentalSnapshot(
            symbol=symbol,
            date=datetime.combine(date, datetime.min.time()),
            name=name or symbol,
            list_date=(
                datetime.combine(list_date, datetime.min.time())
                if list_date is not None else datetime(1990, 1, 1)
            ),
            market_cap=market_cap,
            roe_ttm=roe_ttm, ocf_ttm=ocf_ttm, pe_ratio=pe_ratio, pb_ratio=pb_ratio,
            earnings_growth=earnings_growth, revenue_growth=revenue_growth,
        )
