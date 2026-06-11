"""/api/live/* 实盘留痕只读端点测试 — 临时 trading.db 注入。"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.persistence.trading_store import TradingStore
from src.interfaces.api.app import app
from src.interfaces.api.routes.live import get_trading_db_path

NOW = datetime.now()  # overview 的"今日"统计基于真实时钟, 造数对齐


def _seed(db: str) -> None:
    s = TradingStore(db)
    s.save_cycle_start(cycle_id="c1", cycle_time=NOW.isoformat(),
                       mode="dry_run", strategy="dual_ma")
    s.finalize_cycle(cycle_id="c1", signals_generated=2, orders_submitted=1,
                     orders_rejected=1, orders_failed=0,
                     notional_submitted=500.0)
    s.save_execution({
        "order_id": "o1", "cycle_id": "c1", "mode": "dry_run",
        "symbol": "601006.SH", "direction": "BUY", "signal_price": 5.0,
        "exec_price": 5.0, "volume": 100, "notional": 500.0,
        "status": "DRY_RUN", "reject_reason": None, "strategy_name": "dual_ma",
        "confidence": 0.9, "submitted_at": NOW.isoformat(),
        "final_status_at": None, "status_trail": "[]"})
    s.save_account_snapshot(snapshot_time=NOW.isoformat(), mode="dry_run",
                            total_asset=146000.0, available_cash=140000.0,
                            frozen_cash=0.0, market_value=6000.0)
    s.save_position_snapshots(snapshot_time=NOW.isoformat(), mode="dry_run",
                              rows=[{"symbol": "601006.SH", "total_volume": 100,
                                     "available_volume": 0, "average_cost": 5.05,
                                     "last_price": None}])
    s.close()


@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "trading.db")
    _seed(db)
    app.dependency_overrides[get_trading_db_path] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestLiveRoutes:
    def test_overview(self, client):
        body = client.get("/api/live/overview").json()
        assert body["db_exists"] is True
        assert body["latest_account"]["total_asset"] == 146000.0
        assert body["cycles_today"] == 1
        assert body["executions_today"] == 1

    def test_cycles_and_executions(self, client):
        cycles = client.get("/api/live/cycles").json()["cycles"]
        assert cycles[0]["cycle_id"] == "c1" and cycles[0]["orders_submitted"] == 1
        execs = client.get("/api/live/executions").json()["executions"]
        assert execs[0]["symbol"] == "601006.SH" and execs[0]["status"] == "DRY_RUN"

    def test_positions_and_equity(self, client):
        positions = client.get("/api/live/positions").json()["positions"]
        assert positions[0]["symbol"] == "601006.SH"
        series = client.get("/api/live/equity").json()["series"]
        assert len(series) == 1 and series[0]["total_asset"] == 146000.0

    def test_missing_db_explicit_empty_state(self, tmp_path):
        app.dependency_overrides[get_trading_db_path] = (
            lambda: str(tmp_path / "nonexistent.db"))
        try:
            body = TestClient(app).get("/api/live/overview").json()
            assert body["db_exists"] is False
            assert TestClient(app).get("/api/live/cycles").json() == {"cycles": []}
        finally:
            app.dependency_overrides.clear()
