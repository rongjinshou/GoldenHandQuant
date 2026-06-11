"""TradingStore 测试 — 临时 SQLite 文件，覆盖循环/执行/快照/预算统计。"""
from datetime import datetime

from src.infrastructure.persistence.trading_store import TradingStore

T0 = datetime(2026, 6, 10, 9, 35, 0)


def _store(tmp_path) -> TradingStore:
    return TradingStore(str(tmp_path / "trading.db"))


def _exec_row(order_id="o1", symbol="601006.SH", direction="BUY",
              status="SUBMITTED", notional=500.0, submitted_at=T0) -> dict:
    return {
        "order_id": order_id, "cycle_id": "c1", "mode": "dry_run",
        "symbol": symbol, "direction": direction,
        "signal_price": 5.0, "exec_price": 5.0, "volume": 100,
        "notional": notional, "status": status, "reject_reason": None,
        "strategy_name": "dual_ma", "confidence": 0.8,
        "submitted_at": submitted_at.isoformat(), "final_status_at": None,
        "status_trail": "[]",
    }


class TestCycles:
    def test_start_then_finalize_roundtrip(self, tmp_path):
        s = _store(tmp_path)
        s.save_cycle_start(cycle_id="c1", cycle_time=T0.isoformat(),
                           mode="dry_run", strategy="dual_ma")
        s.finalize_cycle(cycle_id="c1", signals_generated=3, orders_submitted=1,
                         orders_rejected=2, orders_failed=0,
                         notional_submitted=500.0, note="")

        cycles = s.load_cycles(limit=10)

        assert len(cycles) == 1
        assert cycles[0]["orders_submitted"] == 1
        assert cycles[0]["notional_submitted"] == 500.0

    def test_reopen_same_file_is_idempotent(self, tmp_path):
        path = str(tmp_path / "trading.db")
        TradingStore(path).close()
        s = TradingStore(path)
        assert s.load_cycles() == []


class TestExecutions:
    def test_save_is_upsert_by_order_id(self, tmp_path):
        s = _store(tmp_path)
        s.save_execution(_exec_row(status="SUBMITTED"))
        s.save_execution(_exec_row(status="FILLED"))

        rows = s.load_executions(limit=10)

        assert len(rows) == 1
        assert rows[0]["status"] == "FILLED"

    def test_today_submitted_notional_excludes_rejected(self, tmp_path):
        s = _store(tmp_path)
        s.save_execution(_exec_row("o1", status="SUBMITTED", notional=500.0))
        s.save_execution(_exec_row("o2", status="REJECTED", notional=999.0))
        s.save_execution(_exec_row("o3", status="DRY_RUN", notional=300.0))

        total = s.today_submitted_notional(mode="dry_run", today=T0.date().isoformat())

        assert total == 800.0

    def test_today_traded_keys(self, tmp_path):
        s = _store(tmp_path)
        s.save_execution(_exec_row("o1", symbol="601006.SH", direction="BUY"))
        s.save_execution(_exec_row("o2", symbol="600000.SH", direction="SELL",
                                   status="REJECTED"))

        keys = s.today_traded_keys(mode="dry_run", today=T0.date().isoformat())

        assert keys == {"601006.SH:BUY"}  # 拒单不算已交易


class TestSnapshots:
    def test_account_snapshot_and_day_start_equity(self, tmp_path):
        s = _store(tmp_path)
        s.save_account_snapshot(snapshot_time=T0.isoformat(), mode="dry_run",
                                total_asset=146000.0, available_cash=140000.0,
                                frozen_cash=0.0, market_value=6000.0)
        s.save_account_snapshot(snapshot_time=T0.replace(hour=14).isoformat(),
                                mode="dry_run", total_asset=145000.0,
                                available_cash=139000.0, frozen_cash=0.0,
                                market_value=6000.0)

        assert s.day_start_equity(mode="dry_run", today=T0.date().isoformat()) == 146000.0
        series = s.load_account_series(mode="dry_run")
        assert len(series) == 2
        assert series[0]["total_asset"] == 146000.0  # 升序返回

    def test_position_snapshots_latest_batch(self, tmp_path):
        s = _store(tmp_path)
        s.save_position_snapshots(snapshot_time=T0.isoformat(), mode="dry_run", rows=[
            {"symbol": "601006.SH", "total_volume": 100, "available_volume": 0,
             "average_cost": 5.05, "last_price": 5.06},
        ])
        s.save_position_snapshots(snapshot_time=T0.replace(hour=14).isoformat(),
                                  mode="dry_run", rows=[
            {"symbol": "601006.SH", "total_volume": 100, "available_volume": 100,
             "average_cost": 5.05, "last_price": 5.10},
        ])

        latest = s.load_latest_positions(mode="dry_run")

        assert len(latest) == 1
        assert latest[0]["available_volume"] == 100
