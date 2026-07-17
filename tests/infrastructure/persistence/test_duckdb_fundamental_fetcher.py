"""DuckDBFundamentalFetcher 测试 — 放 persistence/ 而非镜像目录 gateway/:
gateway/ 因 QMT 文件导入失败被默认门 --ignore; 本 fetcher 纯 DuckDB 无 QMT, 须在门跑得到处。"""


import duckdb

from src.infrastructure.gateway.duckdb_fundamental_fetcher import DuckDBFundamentalFetcher


def _make_db(path):
    con = duckdb.connect(str(path))
    con.execute(
        """CREATE TABLE fundamental_snapshots(
        symbol VARCHAR, date DATE, source VARCHAR, name VARCHAR, list_date DATE,
        market_cap DOUBLE, roe_ttm DOUBLE, ocf_ttm DOUBLE, pe_ratio DOUBLE,
        pb_ratio DOUBLE, earnings_growth DOUBLE, revenue_growth DOUBLE)"""
    )
    con.executemany(
        "INSERT INTO fundamental_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("000001.SZ", "2024-01-02", "qmt", "平安", "1991-04-03", 3.0e11, 0.1, 1.0, 5.0, 0.8, 0.05, 0.04),
            ("000002.SZ", "2024-01-02", "qmt", "万科", "1991-01-29", 2.0e10, 0.08, 1.0, 6.0, 0.7, 0.02, 0.01),
            # market_cap=0 的数据空洞须被剔除 (设计 DD-7)
            ("000003.SZ", "2024-01-02", "qmt", "空洞", "1991-01-29", 0.0, None, None, None, None, None, None),
            # 2 月行: 用于区间过滤断言
            ("000001.SZ", "2024-02-01", "qmt", "平安", "1991-04-03", 3.1e11, 0.1, 1.0, 5.0, 0.8, 0.05, 0.04),
        ],
    )
    con.close()


def test_fetch_filters_market_cap_zero_and_maps_columns(tmp_path):
    db = tmp_path / "m.duckdb"
    _make_db(db)
    f = DuckDBFundamentalFetcher(str(db))
    try:
        snaps = f.fetch_by_range("2024-01-01", "2024-01-31")
    finally:
        f.close()

    syms = {s.symbol for s in snaps}
    assert syms == {"000001.SZ", "000002.SZ"}  # market_cap=0 的 000003 被剔除
    px = next(s for s in snaps if s.symbol == "000001.SZ")
    assert px.market_cap == 3.0e11 and px.name == "平安"
    assert px.pe_ratio == 5.0 and px.roe_ttm == 0.1
    assert px.date.year == 2024 and px.list_date.year == 1991  # date → datetime 转换


def test_fetch_respects_date_range_and_symbols(tmp_path):
    db = tmp_path / "m.duckdb"
    _make_db(db)
    f = DuckDBFundamentalFetcher(str(db))
    try:
        only_feb = f.fetch_by_range("2024-01-15", "2024-12-31")  # 含 000001 的 2-01 行
        only_wanke = f.fetch_by_range("2024-01-01", "2024-01-31", symbols=["000002.SZ"])
    finally:
        f.close()

    assert {s.date.month for s in only_feb} == {2}
    assert {s.symbol for s in only_wanke} == {"000002.SZ"}


def test_missing_table_returns_empty(tmp_path):
    db = tmp_path / "empty.duckdb"
    duckdb.connect(str(db)).close()
    f = DuckDBFundamentalFetcher(str(db))
    try:
        assert f.fetch_by_range("2024-01-01", "2024-12-31") == []
    finally:
        f.close()
