"""数据质量门禁测试（2026-07-10 六西格玛体检 B3）。"""

from datetime import date, datetime

import pytest

from src.domain.market.services.feature_engine import compute_features
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.infrastructure.persistence.data_quality import (
    FAIL,
    PASS,
    WARN,
    has_failure,
    run_quality_checks,
)
from src.infrastructure.persistence.market_data_store import MarketDataStore


@pytest.fixture
def store():
    s = MarketDataStore(":memory:")
    yield s
    s.close()


def _bars(symbol: str, start: str, n: int) -> list[Bar]:
    from datetime import timedelta
    t0 = datetime.strptime(start, "%Y-%m-%d")
    out = []
    prev_close = 10.0
    for i in range(n):
        close = 10.0 + (i % 7) * 0.3 + i * 0.01  # 有方差的假行情
        out.append(Bar(
            symbol=symbol, timestamp=t0 + timedelta(days=i),
            timeframe=Timeframe.DAY_1,
            open=close - 0.1, high=close + 0.2, low=close - 0.2,
            close=close, volume=1000.0 + i, prev_close=prev_close,
        ))
        prev_close = close
    return out


def _seed_healthy(store: MarketDataStore, symbol="000001.SZ", n=400) -> date:
    """入库 n 天 bars + 对应特征, 返回最新 bar 日期。"""
    bars = _bars(symbol, "2024-01-01", n)
    store.upsert_bars(bars, "qmt")
    df = store.load_bars_df([symbol], "2024-01-01", "2099-01-01", "qmt")
    store.upsert_features_df(compute_features(df), 1)
    return bars[-1].timestamp.date()


def _by_name(results, name):
    return next(r for r in results if r.name == name)


class TestQualityGates:
    def test_healthy_store_all_pass(self, store):
        last = _seed_healthy(store)

        results = run_quality_checks(store, today=last)

        # fundamentals 为空只 WARN, 不构成 FAIL
        assert not has_failure(results)
        assert _by_name(results, "特征成熟区 NULL(固化哨兵)").status == PASS
        assert _by_name(results, "数据新鲜度").status == PASS

    def test_mature_null_ma20_fails(self, store):
        """固化事故哨兵: 成熟区出现 NULL ma_20 必须 FAIL(零容忍)。"""
        last = _seed_healthy(store)
        store._conn.execute(
            """UPDATE stock_features SET ma_20 = NULL
               WHERE date = (SELECT MAX(date) FROM stock_features)"""
        )

        results = run_quality_checks(store, today=last)

        assert _by_name(results, "特征成熟区 NULL(固化哨兵)").status == FAIL
        assert has_failure(results)

    def test_warmup_nulls_do_not_fail(self, store):
        """预热区(次新股)NULL 合法: 只有 30 天历史的股票整窗 NULL 不触发哨兵。"""
        last = _seed_healthy(store)          # 健康主体
        _seed_new_listing(store, last)       # 次新股, ma_20 天然 NULL

        results = run_quality_checks(store, today=last)

        assert _by_name(results, "特征成熟区 NULL(固化哨兵)").status == PASS

    def test_staleness_warn_then_fail(self, store):
        from datetime import timedelta
        last = _seed_healthy(store)

        warn_results = run_quality_checks(store, today=last + timedelta(days=8))
        fail_results = run_quality_checks(store, today=last + timedelta(days=12))

        assert _by_name(warn_results, "数据新鲜度").status == WARN
        assert _by_name(fail_results, "数据新鲜度").status == FAIL

    def test_empty_store_fails_freshness(self, store):
        results = run_quality_checks(store, today=date(2026, 7, 10))

        assert _by_name(results, "数据新鲜度").status == FAIL


def _seed_new_listing(store: MarketDataStore, last: date, symbol="301999.SZ"):
    from datetime import timedelta
    start = (last - timedelta(days=29)).strftime("%Y-%m-%d")
    bars = _bars(symbol, start, 30)
    store.upsert_bars(bars, "qmt")
    df = store.load_bars_df([symbol], start, "2099-01-01", "qmt")
    store.upsert_features_df(compute_features(df), 1)


class TestCrossSourceChecks:
    """C8 市值跨源偏差 / C9 名称新鲜度(0712-mc1 DD-4)。"""

    def _mk_ts(self, path, mv_factor=1.0, fresh_names=True):
        import duckdb
        ts = duckdb.connect(str(path))
        ts.execute("CREATE TABLE ts_daily_basic (ts_code VARCHAR, trade_date VARCHAR, total_mv DOUBLE)")
        ts.execute("CREATE TABLE ts_stock_basic (ts_code VARCHAR, name VARCHAR, list_status VARCHAR)")
        for i in range(20):
            sym = f"6001{i:02d}.SH"
            ts.execute("INSERT INTO ts_daily_basic VALUES (?, '20260710', ?)",
                       [sym, 100.0 * mv_factor])  # 万元
            ts.execute("INSERT INTO ts_stock_basic VALUES (?, ?, 'L')",
                       [sym, f"新名{i}" if not fresh_names else f"名{i}"])
        ts.close()

    def _mk_market(self, con):
        con.execute("""CREATE TABLE IF NOT EXISTS _t AS SELECT 1""")  # noop 防空库
        for i in range(20):
            sym = f"6001{i:02d}.SH"
            con.execute(
                "INSERT INTO fundamental_snapshots VALUES (?, DATE '2026-07-10', 'qmt', ?, "
                "DATE '2000-01-01', ?, NULL,NULL,NULL,NULL,NULL,NULL)",
                [sym, f"名{i}", 100.0 * 1e4])
            con.execute("INSERT INTO instruments VALUES (?, 'qmt', ?, DATE '2000-01-01', NULL, now())",
                        [sym, f"名{i}"])

    def test_cap_check_pass_fail_skip(self, tmp_path):
        from src.infrastructure.persistence.data_quality import check_cap_cross_source
        from src.infrastructure.persistence.market_data_store import MarketDataStore
        store = MarketDataStore(str(tmp_path / "m.duckdb"))
        self._mk_market(store._conn)

        ts_ok = tmp_path / "ts_ok.duckdb"
        self._mk_ts(ts_ok)
        r = check_cap_cross_source(store._conn, str(ts_ok), sample=20)
        assert r.status == "PASS"

        ts_bad = tmp_path / "ts_bad.duckdb"
        self._mk_ts(ts_bad, mv_factor=2.0)   # 全部偏差 50% → FAIL
        r2 = check_cap_cross_source(store._conn, str(ts_bad), sample=20)
        assert r2.status == "FAIL"

        r3 = check_cap_cross_source(store._conn, str(tmp_path / "absent.duckdb"), sample=20)
        assert r3.status == "SKIP"

    def test_name_freshness_warn_and_pass(self, tmp_path):
        from src.infrastructure.persistence.data_quality import check_name_freshness
        from src.infrastructure.persistence.market_data_store import MarketDataStore
        store = MarketDataStore(str(tmp_path / "m2.duckdb"))
        self._mk_market(store._conn)

        ts_stale = tmp_path / "ts_stale.duckdb"
        self._mk_ts(ts_stale, fresh_names=False)   # 20 只名称全不一致
        r = check_name_freshness(store._conn, str(ts_stale), warn_threshold=5)
        assert r.status == "WARN" and "20" in r.detail

        ts_fresh = tmp_path / "ts_fresh.duckdb"
        self._mk_ts(ts_fresh, fresh_names=True)
        r2 = check_name_freshness(store._conn, str(ts_fresh), warn_threshold=5)
        assert r2.status == "PASS"
