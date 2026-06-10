"""MarketDataStore 单测 — upsert 幂等 / 缺口计算 / 版本隔离 / join 读取。"""

from datetime import datetime

import pandas as pd
import pytest

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
from src.domain.market.value_objects.timeframe import Timeframe
from src.infrastructure.persistence.market_data_store import MarketDataStore


@pytest.fixture
def store():
    s = MarketDataStore(":memory:")
    yield s
    s.close()


def _bar(symbol: str, date: str, close: float) -> Bar:
    return Bar(
        symbol=symbol,
        timeframe=Timeframe.DAY_1,
        timestamp=datetime.strptime(date, "%Y-%m-%d"),
        open=close, high=close, low=close, close=close,
        volume=1000.0, prev_close=close,
    )


def _fund(symbol: str, date: str, market_cap: float = 1e9) -> FundamentalSnapshot:
    return FundamentalSnapshot(
        symbol=symbol,
        date=datetime.strptime(date, "%Y-%m-%d"),
        name="测试股",
        list_date=datetime(2010, 1, 1),
        market_cap=market_cap,
    )


class TestDdl:
    def test_reopen_same_file_is_idempotent(self, tmp_path):
        path = str(tmp_path / "m.duckdb")
        s1 = MarketDataStore(path)
        s1.upsert_bars([_bar("A", "2024-01-02", 10.0)], source="qmt")
        s1.close()
        s2 = MarketDataStore(path)  # CREATE IF NOT EXISTS 再跑一遍
        df = s2.load_bars_df(["A"], "2024-01-01", "2024-12-31", source="qmt")
        s2.close()
        assert len(df) == 1


class TestBars:
    def test_upsert_idempotent_and_updates(self, store):
        store.upsert_bars([_bar("A", "2024-01-02", 10.0), _bar("A", "2024-01-03", 11.0)], "qmt")
        store.upsert_bars([_bar("A", "2024-01-02", 10.0)], "qmt")  # 重复插入
        df = store.load_bars_df(["A"], "2024-01-01", "2024-12-31", "qmt")
        assert len(df) == 2

        store.upsert_bars([_bar("A", "2024-01-02", 99.0)], "qmt")  # 同键更新
        df = store.load_bars_df(["A"], "2024-01-02", "2024-01-02", "qmt")
        assert len(df) == 1
        assert df.iloc[0]["close"] == 99.0

    def test_load_filters_by_symbol_and_range(self, store):
        store.upsert_bars(
            [_bar("A", "2024-01-02", 1.0), _bar("A", "2024-02-02", 2.0),
             _bar("B", "2024-01-02", 3.0)],
            "qmt",
        )
        df = store.load_bars_df(["A"], "2024-01-01", "2024-01-31", "qmt")
        assert len(df) == 1
        assert df.iloc[0]["symbol"] == "A"

    def test_sources_are_isolated(self, store):
        store.upsert_bars([_bar("A", "2024-01-02", 1.0)], "qmt")
        store.upsert_bars([_bar("A", "2024-01-02", 2.0)], "tushare")
        qmt = store.load_bars_df(["A"], "2024-01-01", "2024-12-31", "qmt")
        ts = store.load_bars_df(["A"], "2024-01-01", "2024-12-31", "tushare")
        assert qmt.iloc[0]["close"] == 1.0
        assert ts.iloc[0]["close"] == 2.0


class TestFetchMeta:
    def test_no_record_means_full_gap(self, store):
        gaps = store.missing_ranges("qmt", "bars", "A", "2024-01-01", "2024-06-30")
        assert gaps == [("2024-01-01", "2024-06-30")]

    def test_full_coverage_means_no_gap(self, store):
        store.mark_fulfilled("qmt", "bars", "A", "2023-01-01", "2025-01-01")
        gaps = store.missing_ranges("qmt", "bars", "A", "2024-01-01", "2024-06-30")
        assert gaps == []

    def test_left_and_right_gaps(self, store):
        store.mark_fulfilled("qmt", "bars", "A", "2024-03-01", "2024-09-01")
        gaps = store.missing_ranges("qmt", "bars", "A", "2024-01-01", "2024-12-31")
        assert gaps == [("2024-01-01", "2024-02-29"), ("2024-09-02", "2024-12-31")]

    def test_mark_fulfilled_unions_interval(self, store):
        store.mark_fulfilled("qmt", "bars", "A", "2024-03-01", "2024-06-30")
        store.mark_fulfilled("qmt", "bars", "A", "2024-01-01", "2024-04-01")
        assert store.get_fulfilled("qmt", "bars", "A") == ("2024-01-01", "2024-06-30")

    def test_meta_keyed_by_source_table_symbol(self, store):
        store.mark_fulfilled("qmt", "bars", "A", "2024-01-01", "2024-06-30")
        assert store.get_fulfilled("tushare", "bars", "A") is None
        assert store.get_fulfilled("qmt", "stock_features:v1", "A") is None


class TestFeatures:
    def _feature_row(self, symbol: str, date: str, **kw) -> dict:
        row = {
            "symbol": symbol, "date": date,
            "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
            "volume": 100.0, "prev_close": 1.0, "exec_close": 1.1,
            "return_5d": None, "return_20d": None, "return_60d": None,
            "volatility_20d": None, "volatility_60d": None,
            "turnover_rate": None, "avg_turnover_20d": None,
            "rsi_14": None, "macd": None, "macd_signal": None,
            "ma_5": None, "ma_20": None, "ma_60": None,
            "high_20d": None, "low_20d": None, "atr_14": None,
            "skewness_20d": None, "illiquidity_20d": None, "obv_slope_20d": None,
        }
        row.update(kw)
        return row

    def test_version_isolation(self, store):
        store.upsert_features_df(
            pd.DataFrame([self._feature_row("A", "2024-01-02", return_5d=0.1)]),
            feature_version=1,
        )
        store.upsert_features_df(
            pd.DataFrame([self._feature_row("A", "2024-01-02", return_5d=0.9)]),
            feature_version=2,
        )
        store.upsert_fundamentals([_fund("A", "2024-01-02")], "qmt")

        v1 = store.load_feature_join_df(["A"], "2024-01-01", "2024-12-31", 1, "qmt")
        v2 = store.load_feature_join_df(["A"], "2024-01-01", "2024-12-31", 2, "qmt")
        assert len(v1) == 1 and len(v2) == 1
        assert v1.iloc[0]["return_5d"] == 0.1
        assert v2.iloc[0]["return_5d"] == 0.9

    def test_join_requires_fundamentals(self, store):
        """无基本面的 (symbol, date) 不产出截面行 — 与旧管道 fund is None: continue 同语义。"""
        store.upsert_features_df(
            pd.DataFrame([
                self._feature_row("A", "2024-01-02"),
                self._feature_row("B", "2024-01-02"),
            ]),
            feature_version=1,
        )
        store.upsert_fundamentals([_fund("A", "2024-01-02", market_cap=5e9)], "qmt")

        df = store.load_feature_join_df(None, "2024-01-01", "2024-12-31", 1, "qmt")
        assert list(df["symbol"]) == ["A"]
        assert df.iloc[0]["market_cap"] == 5e9

    def test_upsert_features_idempotent(self, store):
        df = pd.DataFrame([self._feature_row("A", "2024-01-02")])
        store.upsert_features_df(df, feature_version=1)
        store.upsert_features_df(df, feature_version=1)
        store.upsert_fundamentals([_fund("A", "2024-01-02")], "qmt")
        out = store.load_feature_join_df(["A"], "2024-01-01", "2024-12-31", 1, "qmt")
        assert len(out) == 1


class TestVerdicts:
    def _rows(self) -> list[dict]:
        return [{
            "factor_id": "F04", "factor_name": "低波动", "expression": "0 - volatility_20d",
            "ic_mean": 0.05, "ir": 0.31, "ic_positive_rate": 0.62,
            "monotonicity_score": 1.0, "long_short_return": 0.15,
            "score": 88.0, "grade": "A",
            "oos_ic_mean": 0.05, "oos_ir": 0.3, "oos_long_short_return": -0.01,
            "passed": False, "reasons": ["样本外多空收益<=0"],
        }]

    def test_insert_and_load_runs_grouped_desc(self, store):
        store.insert_verdicts("20260611-010000", {"start": "2021-01-01"}, self._rows())
        store.insert_verdicts("20260611-020000", {"start": "2021-01-01"}, self._rows())

        runs = store.load_verdict_runs()

        assert [r["run_id"] for r in runs] == ["20260611-020000", "20260611-010000"]
        assert runs[0]["params"]["start"] == "2021-01-01"
        f = runs[0]["factors"][0]
        assert f["factor_id"] == "F04"
        assert f["passed"] is False
        assert f["reasons"] == ["样本外多空收益<=0"]

    def test_insert_idempotent(self, store):
        store.insert_verdicts("r1", {}, self._rows())
        store.insert_verdicts("r1", {}, self._rows())
        assert len(store.load_verdict_runs()) == 1


class TestReadOnly:
    def test_read_only_can_read(self, tmp_path):
        path = str(tmp_path / "m.duckdb")
        rw = MarketDataStore(path)
        rw.upsert_bars([_bar("A", "2024-01-02", 10.0)], "qmt")
        rw.close()

        ro = MarketDataStore(path, read_only=True)
        df = ro.load_bars_df(["A"], "2024-01-01", "2024-12-31", "qmt")
        ro.close()
        assert len(df) == 1


class TestInstruments:
    def test_upsert_and_load_symbols(self, store):
        store.upsert_instruments(
            [
                {"symbol": "000001.SZ", "name": "平安银行",
                 "list_date": "1991-04-03", "delist_date": None},
                {"symbol": "600000.SH", "name": "浦发银行",
                 "list_date": "1999-11-10", "delist_date": None},
            ],
            source="qmt",
        )
        store.upsert_instruments(
            [{"symbol": "000001.SZ", "name": "平安银行",
              "list_date": "1991-04-03", "delist_date": None}],
            source="qmt",
        )
        assert store.load_symbols("qmt") == ["000001.SZ", "600000.SH"]
