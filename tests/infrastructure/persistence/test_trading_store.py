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


class TestThreadSafety:
    def test_usable_from_worker_thread(self, tmp_path):
        """守护模式: store 在主线程创建、在调度线程使用, 不得抛跨线程错误。"""
        import threading

        s = _store(tmp_path)
        errors: list[Exception] = []

        def _work():
            try:
                s.save_cycle_start(cycle_id="t1", cycle_time=T0.isoformat(),
                                   mode="dry_run", strategy="dual_ma")
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        t = threading.Thread(target=_work)
        t.start()
        t.join()

        assert errors == []
        assert len(s.load_cycles()) == 1


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

        total = s.today_submitted_notional(today=T0.date().isoformat())

        assert total == 800.0

    def test_today_notional_counts_canceled_partial_fill(self, tmp_path):
        """PART_CANCEL→CANCELED 的已发意向必须占预算 (评审发现 #5)。"""
        s = _store(tmp_path)
        s.save_execution(_exec_row("o1", status="CANCELED", notional=1400.0))

        assert s.today_submitted_notional(today=T0.date().isoformat()) == 1400.0

    def test_day_level_queries_ignore_mode(self, tmp_path):
        """日级防线跨 mode 统计——dry_run/live 背后是同一真实账户 (评审发现 #9)。"""
        s = _store(tmp_path)
        row = _exec_row("o1", status="DRY_RUN", notional=500.0)
        row["mode"] = "dry_run"
        s.save_execution(row)
        row2 = _exec_row("o2", status="SUBMITTED", notional=300.0)
        row2["mode"] = "live"
        s.save_execution(row2)

        assert s.today_submitted_notional(today=T0.date().isoformat()) == 800.0
        assert s.today_traded_keys(today=T0.date().isoformat()) == {"601006.SH:BUY"}

    def test_today_traded_keys(self, tmp_path):
        s = _store(tmp_path)
        s.save_execution(_exec_row("o1", symbol="601006.SH", direction="BUY"))
        s.save_execution(_exec_row("o2", symbol="600000.SH", direction="SELL",
                                   status="REJECTED"))

        keys = s.today_traded_keys(today=T0.date().isoformat())

        assert keys == {"601006.SH:BUY"}  # 拒单不算已交易


def _snapshot_row(cycle_id="c1", snapshot_time=T0, data_health="ok",
                  note="") -> dict:
    return {
        "cycle_id": cycle_id, "snapshot_time": snapshot_time.isoformat(),
        "mode": "dry_run", "strategy": "micro_value",
        "universe_size": 1885, "filtered_size": 1880,
        "fundamental_date": "2026-06-09T00:00:00", "fundamental_rows": 1880,
        "staleness_days": 1, "index_bars_count": 100, "gate_passed": 1,
        "positions_json": "[]", "total_asset": 146000.0,
        "selection_json": '["601006.SH"]', "targets_json": "[]",
        "data_health": data_health, "note": note,
    }


class TestSignalSnapshots:
    def test_save_and_load_roundtrip(self, tmp_path):
        s = _store(tmp_path)
        s.save_signal_snapshot(_snapshot_row())

        rows = s.load_signal_snapshots(limit=10)

        assert len(rows) == 1
        assert rows[0]["strategy"] == "micro_value"
        assert rows[0]["gate_passed"] == 1
        assert rows[0]["selection_json"] == '["601006.SH"]'
        assert rows[0]["fundamental_date"] == "2026-06-09T00:00:00"

    def test_save_is_upsert_by_cycle_id(self, tmp_path):
        s = _store(tmp_path)
        s.save_signal_snapshot(_snapshot_row(note="first"))
        s.save_signal_snapshot(_snapshot_row(note="second"))

        rows = s.load_signal_snapshots()

        assert len(rows) == 1
        assert rows[0]["note"] == "second"

    def test_load_by_date_returns_latest_of_day(self, tmp_path):
        s = _store(tmp_path)
        s.save_signal_snapshot(_snapshot_row("c-am", snapshot_time=T0))
        s.save_signal_snapshot(
            _snapshot_row("c-pm", snapshot_time=T0.replace(hour=14, minute=50)))
        s.save_signal_snapshot(
            _snapshot_row("c-other", snapshot_time=datetime(2026, 6, 11, 9, 35)))

        row = s.load_signal_snapshot_by_date(T0.date().isoformat())

        assert row is not None
        assert row["cycle_id"] == "c-pm"

    def test_load_by_date_missing_returns_none(self, tmp_path):
        s = _store(tmp_path)
        assert s.load_signal_snapshot_by_date("2026-07-08") is None

    def test_fault_snapshot_roundtrip(self, tmp_path):
        s = _store(tmp_path)
        s.save_signal_snapshot(_snapshot_row(
            data_health="fault", note="宇宙为空: 装配失败或配置错误"))

        row = s.load_signal_snapshot_by_date(T0.date().isoformat())

        assert row["data_health"] == "fault"
        assert "宇宙为空" in row["note"]


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

        assert s.day_start_equity(today=T0.date().isoformat()) == 146000.0
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
