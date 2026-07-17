"""市值口径迁移/同步: 备份幂等/直配/as-of 回填/超 gap 保留/双源兜底(设计 0712-mc1 DD-2/DD-3)。"""
from datetime import date

import duckdb
import pytest

from src.infrastructure.persistence.cap_regime import (
    migrate_market_cap,
    sync_latest_market_cap,
)


def _mk_market(con):
    con.execute("""CREATE TABLE fundamental_snapshots (
        symbol VARCHAR, date DATE, source VARCHAR, name VARCHAR,
        list_date DATE, market_cap DOUBLE, roe_ttm DOUBLE, ocf_ttm DOUBLE,
        pe_ratio DOUBLE, pb_ratio DOUBLE, earnings_growth DOUBLE, revenue_growth DOUBLE)""")
    rows = [
        ("000021.SZ", date(2024, 1, 5), "qmt", 100e8),   # 直配日
        ("000021.SZ", date(2024, 1, 8), "qmt", 101e8),   # ts 缺该日 → as-of 回填(1/5 值)
        ("000021.SZ", date(2024, 3, 8), "qmt", 102e8),   # 距最近 ts 超 gap → 保留
    ]
    for sym, d, src, mc in rows:
        con.execute(
            "INSERT INTO fundamental_snapshots VALUES (?,?,?,?,?,?,NULL,NULL,NULL,NULL,NULL,NULL)",
            [sym, d, src, "深科技", date(2000, 1, 1), mc])


def _mk_ts(path):
    ts = duckdb.connect(path)
    ts.execute("CREATE TABLE ts_daily_basic (ts_code VARCHAR, trade_date VARCHAR, total_mv DOUBLE)")
    ts.execute("INSERT INTO ts_daily_basic VALUES ('000021.SZ','20240105', 1500000)")  # 万元→150亿
    ts.close()


def test_direct_asof_kept_and_idempotent(tmp_path):
    ts_path = str(tmp_path / "ts.duckdb")
    _mk_ts(ts_path)
    con = duckdb.connect(str(tmp_path / "m.duckdb"))
    _mk_market(con)

    stats = migrate_market_cap(con, ts_path)
    assert stats == {"backed_up": 3, "direct": 1, "asof": 1, "kept": 1}
    got = dict(con.execute(
        "SELECT date, market_cap FROM fundamental_snapshots WHERE symbol='000021.SZ'").fetchall())
    assert got[date(2024, 1, 5)] == 1500000 * 1e4          # 直配
    assert got[date(2024, 1, 8)] == 1500000 * 1e4          # as-of 前值
    assert got[date(2024, 3, 8)] == 102e8                   # 超 gap 保留 QMT
    backup = dict(con.execute(
        "SELECT date, market_cap_qmt FROM fundamental_snapshots WHERE symbol='000021.SZ'").fetchall())
    assert backup[date(2024, 1, 5)] == 100e8                # 原值入备份列

    stats2 = migrate_market_cap(con, ts_path)               # 幂等: 备份不重置
    assert stats2["backed_up"] == 0
    assert dict(con.execute(
        "SELECT date, market_cap_qmt FROM fundamental_snapshots WHERE symbol='000021.SZ'"
    ).fetchall())[date(2024, 1, 5)] == 100e8


def _mk_market_today(con):
    _mk_market(con)
    con.execute(
        "INSERT INTO fundamental_snapshots VALUES ('000021.SZ', DATE '2024-03-11', 'qmt', "
        "'深科技', DATE '2000-01-01', 103e8, NULL,NULL,NULL,NULL,NULL,NULL)")
    con.execute("CREATE TABLE bars (symbol VARCHAR, date DATE, source VARCHAR)")
    con.execute("INSERT INTO bars VALUES ('000021.SZ', DATE '2024-03-11', 'qmt')")


def test_sync_primary_then_fallback_then_fail(tmp_path):
    con = duckdb.connect(str(tmp_path / "m2.duckdb"))
    _mk_market_today(con)

    r = sync_latest_market_cap(con, fetch_primary=lambda day: {"000021.SZ": 155e8},
                               fetch_fallback=lambda: None)
    assert r["source"] == "tushare" and r["updated"] == 1 and r["day"] == "2024-03-11"
    assert con.execute(
        "SELECT market_cap FROM fundamental_snapshots WHERE date=DATE '2024-03-11'"
    ).fetchone()[0] == 155e8

    r2 = sync_latest_market_cap(con, fetch_primary=lambda day: None,
                                fetch_fallback=lambda: {"000021.SZ": 156e8})
    assert r2["source"] == "akshare" and r2["updated"] == 1

    with pytest.raises(RuntimeError):
        sync_latest_market_cap(con, fetch_primary=lambda day: None, fetch_fallback=lambda: None)


class TestUpsertNamePreservation:
    """upsert 防降级覆写(MC-1 连环发现): 代码占位名不得覆盖已有真名。"""

    def test_degenerate_name_does_not_clobber_real_name(self):
        from src.infrastructure.persistence.market_data_store import MarketDataStore
        store = MarketDataStore(":memory:")
        store.upsert_instruments(
            [{"symbol": "000021.SZ", "name": "深科技", "list_date": None, "delist_date": None}], "qmt")
        # 宇宙解析路径的占位 upsert(name=symbol) 不应覆盖真名
        store.upsert_instruments(
            [{"symbol": "000021.SZ", "name": "000021.SZ", "list_date": None, "delist_date": None}], "qmt")
        name = store._conn.execute(
            "SELECT name FROM instruments WHERE symbol='000021.SZ'").fetchone()[0]
        assert name == "深科技"

    def test_real_name_still_updates(self):
        from src.infrastructure.persistence.market_data_store import MarketDataStore
        store = MarketDataStore(":memory:")
        store.upsert_instruments(
            [{"symbol": "000021.SZ", "name": "000021.SZ", "list_date": None, "delist_date": None}], "qmt")
        store.upsert_instruments(
            [{"symbol": "000021.SZ", "name": "ST深科技", "list_date": None, "delist_date": None}], "qmt")
        name = store._conn.execute(
            "SELECT name FROM instruments WHERE symbol='000021.SZ'").fetchone()[0]
        assert name == "ST深科技"


class TestMigrateFundamentalFieldGeneric:
    """MC-2: pe/pb 同族迁移复用同一泛化机制(直配/as-of/保留/幂等备份)。"""

    def test_pe_pb_migration(self, tmp_path):
        from src.infrastructure.persistence.cap_regime import migrate_fundamental_field
        ts = duckdb.connect(str(tmp_path / "ts3.duckdb"))
        ts.execute("CREATE TABLE ts_daily_basic (ts_code VARCHAR, trade_date VARCHAR, "
                   "total_mv DOUBLE, pe_ttm DOUBLE, pb DOUBLE)")
        ts.execute("INSERT INTO ts_daily_basic VALUES ('000021.SZ','20240105', 1, 25.5, 3.2)")
        ts.close()
        con = duckdb.connect(str(tmp_path / "m3.duckdb"))
        _mk_market(con)
        con.execute("UPDATE fundamental_snapshots SET pe_ratio=99.0, pb_ratio=9.9")

        s1 = migrate_fundamental_field(con, str(tmp_path / "ts3.duckdb"),
                                       field="pe_ratio", ts_col="pe_ttm",
                                       backup_col="pe_ratio_qmt", scale=1.0)
        s2 = migrate_fundamental_field(con, str(tmp_path / "ts3.duckdb"),
                                       field="pb_ratio", ts_col="pb",
                                       backup_col="pb_ratio_qmt", scale=1.0)
        assert s1["direct"] == 1 and s2["direct"] == 1
        row = con.execute("SELECT pe_ratio, pb_ratio, pe_ratio_qmt FROM fundamental_snapshots "
                          "WHERE date=DATE '2024-01-05'").fetchone()
        assert row == (25.5, 3.2, 99.0)
        # as-of 回填与超 gap 保留
        got = dict(con.execute("SELECT date, pe_ratio FROM fundamental_snapshots").fetchall())
        from datetime import date as d
        assert got[d(2024, 1, 8)] == 25.5     # as-of
        assert got[d(2024, 3, 8)] == 99.0     # 超 gap 保留原值
        # 幂等: 备份列不被重置
        s3 = migrate_fundamental_field(con, str(tmp_path / "ts3.duckdb"),
                                       field="pe_ratio", ts_col="pe_ttm",
                                       backup_col="pe_ratio_qmt", scale=1.0)
        assert s3["backed_up"] == 0


def test_sync_falls_back_to_previous_day_when_today_unpublished(tmp_path):
    """盘中场景(0713 彩排实证): tushare 当日盘后才发布 → 回退最近有数据的交易日。"""
    from src.infrastructure.persistence.cap_regime import sync_latest_market_cap
    con = duckdb.connect(str(tmp_path / "m4.duckdb"))
    _mk_market_today(con)
    con.execute("INSERT INTO fundamental_snapshots VALUES ('000021.SZ', DATE '2024-03-12', 'qmt', "
                "'深科技', DATE '2000-01-01', 104e8, NULL,NULL,NULL,NULL,NULL,NULL)")
    con.execute("INSERT INTO bars VALUES ('000021.SZ', DATE '2024-03-12', 'qmt')")  # 今日(盘中)

    calls = []

    def primary(day):
        calls.append(day)
        return {"000021.SZ": 158e8} if day == "20240311" else None  # 今日无数据, 昨日有

    r = sync_latest_market_cap(con, fetch_primary=primary, fetch_fallback=lambda: None)
    assert calls == ["20240312", "20240311"]          # 先今日后回退
    assert r["day"] == "2024-03-11" and r["source"] == "tushare"
    assert con.execute("SELECT market_cap FROM fundamental_snapshots WHERE date=DATE '2024-03-11'"
                       ).fetchone()[0] == 158e8
    # 今日行未被动(等盘后/明晨链自然覆盖)
    assert con.execute("SELECT market_cap FROM fundamental_snapshots WHERE date=DATE '2024-03-12'"
                       ).fetchone()[0] == 104e8
