"""DuckDB 市场数据仓储 — instruments/bars/基本面/截面特征/履约元数据。

与交易事务库（SQLite, database.py）分离：本库为列存分析负载（全表扫描 +
零拷贝进 pandas）。设计文档:
docs/feat/0611-market-data-store/2026-06-11-market-data-store-design.md
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from src.domain.market.services.feature_engine import FEATURE_COLUMNS
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot

_DDL_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS instruments (
        symbol      VARCHAR NOT NULL,
        source      VARCHAR NOT NULL,
        name        VARCHAR NOT NULL,
        list_date   DATE,
        delist_date DATE,
        updated_at  TIMESTAMP NOT NULL,
        PRIMARY KEY (symbol, source)
    )""",
    """CREATE TABLE IF NOT EXISTS bars (
        symbol     VARCHAR NOT NULL,
        date       DATE NOT NULL,
        source     VARCHAR NOT NULL,
        open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
        volume     DOUBLE,
        prev_close DOUBLE,
        PRIMARY KEY (symbol, date, source)
    )""",
    """CREATE TABLE IF NOT EXISTS fundamental_snapshots (
        symbol VARCHAR NOT NULL,
        date   DATE NOT NULL,
        source VARCHAR NOT NULL,
        name VARCHAR, list_date DATE,
        market_cap DOUBLE,
        roe_ttm DOUBLE, ocf_ttm DOUBLE,
        pe_ratio DOUBLE, pb_ratio DOUBLE,
        earnings_growth DOUBLE, revenue_growth DOUBLE,
        PRIMARY KEY (symbol, date, source)
    )""",
    f"""CREATE TABLE IF NOT EXISTS stock_features (
        symbol VARCHAR NOT NULL,
        date   DATE NOT NULL,
        feature_version INTEGER NOT NULL,
        {", ".join(f"{c} DOUBLE" for c in FEATURE_COLUMNS if c not in ("symbol", "date"))},
        PRIMARY KEY (symbol, date, feature_version)
    )""",
    """CREATE TABLE IF NOT EXISTS fetch_meta (
        source     VARCHAR NOT NULL,
        table_name VARCHAR NOT NULL,
        symbol     VARCHAR NOT NULL,
        fulfilled_start DATE NOT NULL,
        fulfilled_end   DATE NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        PRIMARY KEY (source, table_name, symbol)
    )""",
)

_FUND_COLS = (
    "name", "list_date", "market_cap", "roe_ttm", "ocf_ttm",
    "pe_ratio", "pb_ratio", "earnings_growth", "revenue_growth",
)
# stock_features 中除主键外的数值列（与 FEATURE_COLUMNS 对齐）
_FEATURE_VALUE_COLS = tuple(c for c in FEATURE_COLUMNS if c not in ("symbol", "date"))


def _day_shift(date_str: str, days: int) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")


class MarketDataStore:
    """市场数据 DuckDB 仓储。日期参数/返回值统一 'YYYY-MM-DD' 字符串。"""

    def __init__(self, db_path: str = "data/market.duckdb") -> None:
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(db_path)
        for stmt in _DDL_STATEMENTS:
            self._conn.execute(stmt)

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------ #
    # instruments
    # ------------------------------------------------------------------ #

    def upsert_instruments(self, instruments: list[dict], source: str) -> None:
        if not instruments:
            return
        df = pd.DataFrame(instruments)
        df["source"] = source
        df["updated_at"] = datetime.now()
        self._conn.register("_inst_in", df)
        self._conn.execute(
            """INSERT OR REPLACE INTO instruments
               (symbol, source, name, list_date, delist_date, updated_at)
               SELECT symbol, source, name,
                      CAST(list_date AS DATE), CAST(delist_date AS DATE), updated_at
               FROM _inst_in"""
        )
        self._conn.unregister("_inst_in")

    def load_symbols(self, source: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT symbol FROM instruments WHERE source = ? ORDER BY symbol", [source]
        ).fetchall()
        return [r[0] for r in rows]

    # ------------------------------------------------------------------ #
    # bars
    # ------------------------------------------------------------------ #

    def upsert_bars(self, bars: list[Bar], source: str) -> None:
        if not bars:
            return
        df = pd.DataFrame({
            "symbol": [b.symbol for b in bars],
            "date": [b.timestamp for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
            "prev_close": [b.prev_close for b in bars],
        })
        df["source"] = source
        self._conn.register("_bars_in", df)
        self._conn.execute(
            """INSERT OR REPLACE INTO bars
               (symbol, date, source, open, high, low, close, volume, prev_close)
               SELECT symbol, CAST(date AS DATE), source,
                      open, high, low, close, volume, prev_close
               FROM _bars_in"""
        )
        self._conn.unregister("_bars_in")

    def load_bars_df(
        self,
        symbols: list[str] | None,
        start_date: str,
        end_date: str,
        source: str,
    ) -> pd.DataFrame:
        """前复权日线长表，列: symbol/date/open/high/low/close/volume/prev_close。"""
        sql = """SELECT symbol, date, open, high, low, close, volume, prev_close
                 FROM bars
                 WHERE source = ?
                   AND date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)"""
        params: list = [source, start_date, end_date]
        sql, params = self._with_symbol_filter(sql, params, symbols, "symbol")
        df = self._conn.execute(sql + " ORDER BY symbol, date", params).df()
        df["date"] = pd.to_datetime(df["date"])
        return df

    # ------------------------------------------------------------------ #
    # fundamentals
    # ------------------------------------------------------------------ #

    def upsert_fundamentals(self, snaps: list[FundamentalSnapshot], source: str) -> None:
        if not snaps:
            return
        df = pd.DataFrame({
            "symbol": [s.symbol for s in snaps],
            "date": [s.date for s in snaps],
            "name": [s.name for s in snaps],
            "list_date": [s.list_date for s in snaps],
            "market_cap": [s.market_cap for s in snaps],
            "roe_ttm": [s.roe_ttm for s in snaps],
            "ocf_ttm": [s.ocf_ttm for s in snaps],
            "pe_ratio": [s.pe_ratio for s in snaps],
            "pb_ratio": [s.pb_ratio for s in snaps],
            "earnings_growth": [s.earnings_growth for s in snaps],
            "revenue_growth": [s.revenue_growth for s in snaps],
        })
        df["source"] = source
        self._conn.register("_fund_in", df)
        self._conn.execute(
            f"""INSERT OR REPLACE INTO fundamental_snapshots
                (symbol, date, source, {", ".join(_FUND_COLS)})
                SELECT symbol, CAST(date AS DATE), source,
                       name, CAST(list_date AS DATE), market_cap, roe_ttm, ocf_ttm,
                       pe_ratio, pb_ratio, earnings_growth, revenue_growth
                FROM _fund_in"""
        )
        self._conn.unregister("_fund_in")

    # ------------------------------------------------------------------ #
    # features
    # ------------------------------------------------------------------ #

    def upsert_features_df(self, df: pd.DataFrame, feature_version: int) -> None:
        """df 列须含 FEATURE_COLUMNS（feature_engine 输出）。"""
        if df.empty:
            return
        ins = df[list(FEATURE_COLUMNS)].copy()
        ins["feature_version"] = feature_version
        self._conn.register("_feat_in", ins)
        self._conn.execute(
            f"""INSERT OR REPLACE INTO stock_features
                (symbol, date, feature_version, {", ".join(_FEATURE_VALUE_COLS)})
                SELECT symbol, CAST(date AS DATE), feature_version,
                       {", ".join(_FEATURE_VALUE_COLS)}
                FROM _feat_in"""
        )
        self._conn.unregister("_feat_in")

    def load_feature_join_df(
        self,
        symbols: list[str] | None,
        start_date: str,
        end_date: str,
        feature_version: int,
        source: str,
    ) -> pd.DataFrame:
        """特征 ⋈ 基本面（INNER：无基本面的快照不产截面行，与旧管道同语义）。"""
        sql = f"""SELECT f.symbol, f.date, {", ".join(f"f.{c}" for c in _FEATURE_VALUE_COLS)},
                         fs.name, fs.list_date, fs.market_cap, fs.roe_ttm, fs.ocf_ttm,
                         fs.pe_ratio, fs.pb_ratio, fs.earnings_growth, fs.revenue_growth
                  FROM stock_features f
                  JOIN fundamental_snapshots fs
                    ON fs.symbol = f.symbol AND fs.date = f.date AND fs.source = ?
                  WHERE f.feature_version = ?
                    AND f.date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)"""
        params: list = [source, feature_version, start_date, end_date]
        sql, params = self._with_symbol_filter(sql, params, symbols, "f.symbol")
        df = self._conn.execute(sql + " ORDER BY f.date, f.symbol", params).df()
        df["date"] = pd.to_datetime(df["date"])
        return df

    def feature_symbols_at(self, feature_version: int) -> set[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT symbol FROM stock_features WHERE feature_version = ?",
            [feature_version],
        ).fetchall()
        return {r[0] for r in rows}

    # ------------------------------------------------------------------ #
    # fetch_meta（履约区间）
    # ------------------------------------------------------------------ #

    def get_fulfilled(self, source: str, table_name: str, symbol: str) -> tuple[str, str] | None:
        row = self._conn.execute(
            """SELECT fulfilled_start, fulfilled_end FROM fetch_meta
               WHERE source = ? AND table_name = ? AND symbol = ?""",
            [source, table_name, symbol],
        ).fetchone()
        if row is None:
            return None
        return row[0].strftime("%Y-%m-%d"), row[1].strftime("%Y-%m-%d")

    def missing_ranges(
        self, source: str, table_name: str, symbol: str, start_date: str, end_date: str
    ) -> list[tuple[str, str]]:
        """请求 [start, end] 相对已履约区间的缺口（0/1/2 段）。

        区间并集语义假设请求相邻或重叠（与 csv _fetch_meta.json 同口径），
        跳跃式请求会产生虚假覆盖，明示不支持。
        """
        fulfilled = self.get_fulfilled(source, table_name, symbol)
        if fulfilled is None:
            return [(start_date, end_date)]
        fs, fe = fulfilled
        gaps: list[tuple[str, str]] = []
        if start_date < fs:
            gaps.append((start_date, _day_shift(fs, -1)))
        if end_date > fe:
            gaps.append((_day_shift(fe, 1), end_date))
        return gaps

    def mark_fulfilled(
        self, source: str, table_name: str, symbol: str, start_date: str, end_date: str
    ) -> None:
        existing = self.get_fulfilled(source, table_name, symbol)
        if existing is not None:
            start_date = min(start_date, existing[0])
            end_date = max(end_date, existing[1])
        self._conn.execute(
            """INSERT OR REPLACE INTO fetch_meta
               (source, table_name, symbol, fulfilled_start, fulfilled_end, updated_at)
               VALUES (?, ?, ?, CAST(? AS DATE), CAST(? AS DATE), ?)""",
            [source, table_name, symbol, start_date, end_date, datetime.now()],
        )

    # ------------------------------------------------------------------ #
    # 概览
    # ------------------------------------------------------------------ #

    def table_stats(self) -> dict[str, dict]:
        """各表行数/标的数/日期范围（quant data status 用）。"""
        stats: dict[str, dict] = {}
        for table in ("instruments", "bars", "fundamental_snapshots", "stock_features"):
            date_col = "list_date" if table == "instruments" else "date"
            row = self._conn.execute(
                f"""SELECT COUNT(*), COUNT(DISTINCT symbol),
                           MIN({date_col}), MAX({date_col})
                    FROM {table}"""
            ).fetchone()
            stats[table] = {
                "rows": row[0],
                "symbols": row[1],
                "min_date": str(row[2]) if row[2] else None,
                "max_date": str(row[3]) if row[3] else None,
            }
        return stats

    # ------------------------------------------------------------------ #

    def _with_symbol_filter(
        self, sql: str, params: list, symbols: list[str] | None, column: str
    ) -> tuple[str, list]:
        if symbols is None:
            return sql, params
        placeholders = ", ".join("?" for _ in symbols)
        return f"{sql} AND {column} IN ({placeholders})", params + list(symbols)
    # 注: symbols 走 SQL 占位符 (全市场 ~5200 只在 DuckDB 参数上限内);
    # 若未来超限可改为 register 临时表 JOIN。
