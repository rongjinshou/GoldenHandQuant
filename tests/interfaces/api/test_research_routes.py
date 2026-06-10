"""/api/research/* 只读端点测试 — TestClient + 临时 DuckDB 注入。"""

from datetime import datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.domain.market.services.feature_engine import FEATURE_COLUMNS, FEATURE_VERSION
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.infrastructure.persistence.market_data_store import MarketDataStore
from src.interfaces.api.app import app
from src.interfaces.api.routes.research import get_research_store


def _bar(symbol: str, date: str, close: float) -> Bar:
    return Bar(
        symbol=symbol,
        timeframe=Timeframe.DAY_1,
        timestamp=datetime.strptime(date, "%Y-%m-%d"),
        open=close - 0.5, high=close + 1, low=close - 1, close=close,
        volume=1000.0, prev_close=close,
    )


def _feature_df(symbol: str, date: str) -> pd.DataFrame:
    row = dict.fromkeys(FEATURE_COLUMNS)
    row.update({
        "symbol": symbol, "date": date,
        "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
        "volume": 100.0, "prev_close": 1.0, "exec_close": 1.1,
        "return_20d": 0.05, "volatility_20d": 0.02,
    })
    return pd.DataFrame([row])


def _verdict_rows() -> list[dict]:
    return [{
        "factor_id": "F04", "factor_name": "低波动", "expression": "0 - volatility_20d",
        "ic_mean": 0.05, "ir": 0.31, "ic_positive_rate": 0.62,
        "monotonicity_score": 1.0, "long_short_return": 0.15,
        "score": 88.0, "grade": "A",
        "oos_ic_mean": 0.05, "oos_ir": 0.3, "oos_long_short_return": -0.01,
        "passed": False, "reasons": ["样本外多空收益<=0"],
    }]


@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "m.duckdb")
    s = MarketDataStore(db)
    s.upsert_instruments(
        [{"symbol": "000001.SZ", "name": "平安银行",
          "list_date": "1991-04-03", "delist_date": None}],
        "qmt",
    )
    s.upsert_bars(
        [_bar("000001.SZ", f"2024-01-{d:02d}", 10.0 + d) for d in range(2, 12)], "qmt"
    )
    s.upsert_features_df(_feature_df("000001.SZ", "2024-01-05"), feature_version=FEATURE_VERSION)
    s.insert_verdicts("r1", {"start": "2021-01-01"}, _verdict_rows())
    s.close()

    def _override():
        store = MarketDataStore(db, read_only=True)
        try:
            yield store
        finally:
            store.close()

    app.dependency_overrides[get_research_store] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestOverview:
    def test_overview(self, client):
        resp = client.get("/api/research/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["db_exists"] is True
        assert body["feature_version"] == FEATURE_VERSION
        assert body["tables"]["bars"]["rows"] == 10
        assert body["tables"]["bars"]["symbols"] == 1
        assert body["verdict_runs"] == 1

    def test_empty_db_overview_zero(self, tmp_path):
        db = str(tmp_path / "empty.duckdb")
        MarketDataStore(db).close()  # 建表后关闭

        def _override():
            store = MarketDataStore(db, read_only=True)
            try:
                yield store
            finally:
                store.close()

        app.dependency_overrides[get_research_store] = _override
        try:
            resp = TestClient(app).get("/api/research/overview")
            assert resp.status_code == 200
            assert resp.json()["tables"]["bars"]["rows"] == 0
        finally:
            app.dependency_overrides.clear()


class TestVerdictsEndpoint:
    def test_verdicts_grouped(self, client):
        resp = client.get("/api/research/verdicts")
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        assert len(runs) == 1
        assert runs[0]["run_id"] == "r1"
        f = runs[0]["factors"][0]
        assert f["factor_id"] == "F04"
        assert f["passed"] is False
        assert f["reasons"] == ["样本外多空收益<=0"]


class TestSymbols:
    def test_prefix_search(self, client):
        resp = client.get("/api/research/symbols", params={"q": "000"})
        assert resp.status_code == 200
        assert resp.json() == [{"symbol": "000001.SZ", "name": "平安银行"}]

    def test_name_search(self, client):
        resp = client.get("/api/research/symbols", params={"q": "平安"})
        assert resp.json()[0]["symbol"] == "000001.SZ"

    def test_no_match(self, client):
        resp = client.get("/api/research/symbols", params={"q": "999"})
        assert resp.json() == []


class TestBars:
    def test_echarts_shape(self, client):
        resp = client.get(
            "/api/research/bars/000001.SZ",
            params={"start": "2024-01-01", "end": "2024-12-31"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["dates"]) == len(body["ohlc"]) == len(body["volume"]) == 10
        assert body["dates"][0] == "2024-01-02"
        # [open, close, low, high]
        assert body["ohlc"][0] == [11.5, 12.0, 11.0, 13.0]

    def test_unknown_symbol_empty(self, client):
        resp = client.get(
            "/api/research/bars/999999.SZ",
            params={"start": "2024-01-01", "end": "2024-12-31"},
        )
        assert resp.json()["dates"] == []


class TestFeatures:
    def test_series(self, client):
        resp = client.get(
            "/api/research/features/000001.SZ",
            params={"names": "return_20d,volatility_20d",
                    "start": "2024-01-01", "end": "2024-12-31"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["dates"] == ["2024-01-05"]
        assert body["series"]["return_20d"] == [0.05]
        # 未算出的特征为 null 而非 NaN（JSON 合法性）
        assert body["series"]["volatility_20d"] == [0.02]

    def test_unknown_feature_name_422(self, client):
        resp = client.get(
            "/api/research/features/000001.SZ",
            params={"names": "not_a_feature"},
        )
        assert resp.status_code == 422
