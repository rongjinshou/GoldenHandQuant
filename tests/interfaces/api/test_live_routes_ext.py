"""live 路由扩展测试 — tmp sqlite + tmp yaml, 全部依赖可覆写。"""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.interfaces.api.app import app
from src.interfaces.api.routes.live import (
    get_trade_logs_dir,
    get_trading_config_path,
    get_trading_db_path,
)

_DDL = """
CREATE TABLE trading_cycles (cycle_id TEXT PRIMARY KEY, cycle_time TEXT, mode TEXT,
  strategy TEXT, signals_generated INTEGER, orders_submitted INTEGER,
  orders_rejected INTEGER, orders_failed INTEGER, notional_submitted REAL, note TEXT);
CREATE TABLE execution_records (order_id TEXT PRIMARY KEY, cycle_id TEXT, mode TEXT,
  symbol TEXT, direction TEXT, exec_price REAL, volume INTEGER, notional REAL,
  status TEXT, reject_reason TEXT, confidence REAL, submitted_at TEXT);
CREATE TABLE position_snapshots (snapshot_time TEXT, mode TEXT, symbol TEXT,
  total_volume INTEGER, available_volume INTEGER, average_cost REAL, last_price REAL);
CREATE TABLE account_snapshots (snapshot_time TEXT, mode TEXT, total_asset REAL,
  available_cash REAL, frozen_cash REAL, market_value REAL);
CREATE TABLE audit_logs (log_id TEXT PRIMARY KEY, user_id TEXT, action TEXT,
  resource_type TEXT, resource_id TEXT, timestamp TEXT, details TEXT, ip_address TEXT);
"""


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "trading.db"
    conn = sqlite3.connect(path)
    conn.executescript(_DDL)
    today = __import__("datetime").date.today().isoformat()
    conn.executemany(
        "INSERT INTO execution_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("o1", "c1", "dry_run", "600000.SH", "BUY", 10.0, 100, 1000.0,
             "DRY_RUN", None, 0.8, f"{today} 09:35:01"),
            ("o2", "c1", "dry_run", "000021.SZ", "BUY", 5.0, 100, 500.0,
             "REJECTED", "notional_cap", 0.7, f"{today} 09:35:02"),
            ("o3", "c2", "live", "600000.SH", "BUY", 10.0, 100, 1000.0,
             "FILLED", None, 0.9, f"{today} 14:50:01"),
        ])
    conn.executemany(
        "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?)",
        [
            ("a1", "auto-trade", "cycle_start", "cycle", "c1",
             f"{today} 09:35:00", "{}", None),
            ("a2", "auto-trade", "place_order", "order", "o1",
             f"{today} 09:35:01", json.dumps({"symbol": "600000.SH"}), None),
        ])
    conn.executemany(
        "INSERT INTO trading_cycles VALUES (?,?,?,?,?,?,?,?,?,?)",
        [("c1", f"{today} 09:35:00", "dry_run", "dual_ma", 3, 1, 1, 0, 1000.0, "")])
    conn.executemany(
        "INSERT INTO position_snapshots VALUES (?,?,?,?,?,?,?)",
        [
            (f"{today} 09:36:00", "dry_run", "600000.SH", 100, 0, 10.0, 10.1),
            (f"{today} 14:51:00", "live", "000021.SZ", 200, 200, 5.0, 5.2),
        ])
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture()
def cfg_path(tmp_path: Path) -> str:
    path = tmp_path / "trading.yaml"
    path.write_text(
        "auto_trade:\n"
        "  enabled: false\n"
        "  mode: dry_run\n"
        "  strategy: dual_ma\n"
        "  symbols: [\"600000.SH\"]\n"
        "  execution_times: [\"09:35\", \"14:50\"]\n"
        "  per_order_notional_cap: 1500.0\n"
        "  daily_notional_cap: 3000.0\n",
        encoding="utf-8")
    return str(path)


@pytest.fixture()
def client(db_path: str, cfg_path: str, tmp_path: Path):
    tickets = tmp_path / "trade_logs"
    tickets.mkdir()
    (tickets / "20260611-130232-601006.SH.json").write_text(
        json.dumps({"symbol": "601006.SH", "status": "FILLED"}), encoding="utf-8")
    app.dependency_overrides[get_trading_db_path] = lambda: db_path
    app.dependency_overrides[get_trading_config_path] = lambda: cfg_path
    app.dependency_overrides[get_trade_logs_dir] = lambda: str(tickets)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class TestAudit:
    def test_lists_logs_desc(self, client) -> None:
        logs = client.get("/api/live/audit").json()["logs"]
        assert [r["log_id"] for r in logs] == ["a2", "a1"]

    def test_action_filter(self, client) -> None:
        logs = client.get("/api/live/audit?action=cycle_start").json()["logs"]
        assert len(logs) == 1 and logs[0]["action"] == "cycle_start"

    def test_missing_db_empty(self, client, db_path) -> None:
        app.dependency_overrides[get_trading_db_path] = lambda: "/nope/x.db"
        assert client.get("/api/live/audit").json() == {"logs": []}


class TestBudget:
    def test_mirrors_trading_store_semantics(self, client) -> None:
        body = client.get("/api/live/budget").json()
        # o1(DRY_RUN)+o3(FILLED) 计入, o2(REJECTED) 不计 — 镜像 _BUDGET_STATUSES
        assert body["submitted_notional"] == 2000.0
        assert body["daily_notional_cap"] == 3000.0
        assert body["remaining"] == 1000.0
        assert body["per_order_notional_cap"] == 1500.0


class TestConfig:
    def test_config_and_slots(self, client) -> None:
        body = client.get("/api/live/config").json()
        assert body["auto_trade"]["mode"] == "dry_run"
        assert body["auto_trade"]["enabled"] is False
        assert body["today"]["expected_slots"] == ["09:35", "14:50"]
        assert body["today"]["cycles_today"] == 1

    def test_missing_yaml_graceful(self, client) -> None:
        app.dependency_overrides[get_trading_config_path] = lambda: "/nope/y.yaml"
        body = client.get("/api/live/config").json()
        assert body["config_exists"] is False
