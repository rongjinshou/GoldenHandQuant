"""build_backtest_cross_section 测试 — DuckDB 源全市场宇宙(无随机500截断) + 离线基本面。"""

from datetime import datetime

import duckdb

from src.interfaces.cli._backtest_wiring import build_backtest_cross_section


def _seed(path, n_symbols=600):
    """造 >500 只 instruments + 当日基本面, 验证不被随机 500 截断。"""
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE instruments(symbol VARCHAR, source VARCHAR, name VARCHAR, "
        "list_date DATE, delist_date DATE, updated_at TIMESTAMP)"
    )
    con.execute(
        """CREATE TABLE fundamental_snapshots(
        symbol VARCHAR, date DATE, source VARCHAR, name VARCHAR, list_date DATE,
        market_cap DOUBLE, roe_ttm DOUBLE, ocf_ttm DOUBLE, pe_ratio DOUBLE,
        pb_ratio DOUBLE, earnings_growth DOUBLE, revenue_growth DOUBLE)"""
    )
    syms = [f"{i:06d}.SZ" for i in range(n_symbols)]
    con.executemany(
        "INSERT INTO instruments VALUES (?,?,?,?,?,?)",
        [(s, "qmt", s, None, None, None) for s in syms],
    )
    con.executemany(
        "INSERT INTO fundamental_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (s, "2024-01-02", "qmt", s, None, 1e9 + i, None, None, None, None, None, None)
            for i, s in enumerate(syms)
        ],
    )
    con.close()


def test_duckdb_source_full_universe_no_500_cap(tmp_path):
    db = tmp_path / "m.duckdb"
    _seed(db, n_symbols=600)
    registry, universe = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", "2024-01-01", "2024-01-31",
        config_symbols=["000852.SH"], db_path=str(db),
    )
    assert len(universe) == 600  # 未被随机 500 截断
    assert len(registry.get_all_at_date(datetime(2024, 1, 2))) == 600


def _seed_akshare_delisted(path, n=3):
    """追加 akshare 源退市股(与 qmt 宇宙不重叠), 验证 include_sources 开关。"""
    con = duckdb.connect(str(path))
    syms = [f"9{i:05d}.SH" for i in range(n)]
    con.executemany(
        "INSERT INTO instruments VALUES (?,?,?,?,?,?)",
        [(s, "akshare", s, None, "2023-06-01", None) for s in syms],
    )
    con.executemany(
        "INSERT INTO fundamental_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [(s, "2024-01-02", "akshare", s, None, 5e8, 0.1, 1e7, None, None, None, None)
         for s in syms],
    )
    con.close()


def test_include_sources_default_excludes_akshare(tmp_path):
    db = tmp_path / "m.duckdb"
    _seed(db, n_symbols=10)
    _seed_akshare_delisted(db, n=3)
    _, universe = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", "2024-01-01", "2024-01-31",
        config_symbols=[], db_path=str(db),
    )
    assert len(universe) == 10  # 默认行为零变化: akshare 源不进宇宙


def test_include_sources_extends_universe_with_delisted(tmp_path):
    db = tmp_path / "m.duckdb"
    _seed(db, n_symbols=10)
    _seed_akshare_delisted(db, n=3)
    registry, universe = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", "2024-01-01", "2024-01-31",
        config_symbols=[], db_path=str(db),
        include_sources=("qmt", "akshare"),
    )
    assert len(universe) == 13
    assert "900000.SH" in universe
    day_rows = registry.get_all_at_date(datetime(2024, 1, 2))
    assert any(s.symbol == "900000.SH" and s.roe_ttm == 0.1 for s in day_rows)


def test_max_universe_explicit_cap(tmp_path):
    db = tmp_path / "m.duckdb"
    _seed(db, n_symbols=600)
    _, universe = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", "2024-01-01", "2024-01-31",
        config_symbols=[], db_path=str(db), max_universe=100,
    )
    assert len(universe) <= 100
