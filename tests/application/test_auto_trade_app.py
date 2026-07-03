"""AutoTradeAppService 测试 — 全链路 dry-run、各闸拒单、预算/亏损/去重/超时撤单。"""
import json
from datetime import datetime

from src.application.auto_trade_app import AutoTradeAppService, AutoTradeConfig
from src.application.data_health import DataHealthError
from src.application.live_signal_service import ScanSnapshot, SignalDisplay
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.common.services.audit_service import AuditService
from src.domain.market.value_objects.quote import Quote
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.infrastructure.persistence.repositories.audit_log_repository import (
    SqliteAuditLogRepository,
)
from src.infrastructure.persistence.trading_store import TradingStore

NOW = datetime(2026, 6, 10, 9, 35)  # 周三盘中


def _display(symbol="601006.SH", direction=SignalDirection.BUY,
             confidence=0.9, price=5.0, volume=100) -> SignalDisplay:
    return SignalDisplay(symbol=symbol, direction=direction, current_price=price,
                         suggested_price=price, suggested_volume=volume,
                         required_capital=price * volume, reason="test",
                         strategy_name="dual_ma", confidence_score=confidence)


class FakeSignalService:
    def __init__(self, displays):
        self._displays = displays

    def scan(self, strategy_name, symbols):
        return self._displays


def _scan_snapshot(*, data_health="ok", note="", gate_passed=True,
                   positions=None, selection=None, targets=None,
                   total_asset=146000.0) -> ScanSnapshot:
    return ScanSnapshot(
        snapshot_time=NOW, strategy="micro_value",
        universe_size=1885, filtered_size=1880,
        fundamental_date=datetime(2026, 6, 9), fundamental_rows=1880,
        staleness_days=1, index_bars_count=100, gate_passed=gate_passed,
        positions=positions if positions is not None else [
            {"symbol": "601006.SH", "total_volume": 100,
             "available_volume": 100, "average_cost": 5.0}],
        total_asset=total_asset,
        selection=selection if selection is not None else ["601006.SH"],
        targets=targets if targets is not None else [
            {"symbol": "601006.SH", "direction": "BUY", "volume": 100,
             "price": 5.0, "strategy_name": "micro_value"}],
        data_health=data_health, note=note)


class SnapshotSignalService(FakeSignalService):
    """scan 成功且填充 last_snapshot 的替身 — 截面路径(LiveSignalService)行为。"""

    def __init__(self, displays, snapshot):
        super().__init__(displays)
        self._snapshot = snapshot
        self.last_snapshot = None

    def scan(self, strategy_name, symbols):
        self.last_snapshot = self._snapshot
        return super().scan(strategy_name, symbols)


class FakeQuotes:
    def __init__(self, quote=None):
        self._q = quote if quote is not None else Quote(
            symbol="601006.SH", last=5.0, bid1=4.99, ask1=5.0,
            prev_close=5.0, timestamp=NOW)

    def subscribe_first_tick(self, symbol, timeout=3.0):
        return self._q


class FakeTradeGateway:
    """终态可编程的网关替身。

    statuses=None(默认) → 永远 DRY_RUN(终态, 多单不卡轮询);
    statuses=() → 永远 ALIVE(配 poll_timeout=0 测超时撤单);
    statuses=[...] → 依次弹出, 耗尽后 ALIVE。
    """

    is_dry_run = True  # 测试默认按 dry_run 语义(返回 DRY_RUN 终态)

    def __init__(self, statuses=None, place_id="gw-1"):
        self.placed: list = []
        self.canceled: list[str] = []
        self._statuses = None if statuses is None else list(statuses)
        self._place_id = place_id

    def place_order(self, order):
        self.placed.append(order)
        return self._place_id

    def query_order_status(self, order_id):
        if self._statuses is None:
            return "DRY_RUN"
        return self._statuses.pop(0) if self._statuses else "ALIVE"

    def cancel_order(self, order_id):
        self.canceled.append(order_id)
        return True


class FakeAccount:
    def __init__(self, cash=100000.0, total=146000.0, positions=()):
        self._asset = Asset(account_id="t", total_asset=total,
                            available_cash=cash, frozen_cash=0.0)
        self._positions = list(positions)

    def get_asset(self):
        return self._asset

    def get_positions(self):
        return self._positions


def _service(tmp_path, *, displays, trade_gw=None, account=None, config=None):
    store = TradingStore(str(tmp_path / "t.db"))
    gw = trade_gw if trade_gw is not None else FakeTradeGateway()
    svc = AutoTradeAppService(
        signal_service=FakeSignalService(displays),
        quote_fetcher=FakeQuotes(),
        trade_gateway=gw,
        account_gateway=account or FakeAccount(),
        store=store,
        audit=AuditService(SqliteAuditLogRepository(store.db)),
        config=config or AutoTradeConfig(mode="dry_run"),
        clock=lambda: NOW,
        sleep=lambda s: None,
    )
    return svc, store, gw


class TestHappyPath:
    def test_full_cycle_persists_everything(self, tmp_path):
        svc, store, gw = _service(tmp_path, displays=[_display()])

        summary = svc.run_cycle()

        assert summary.orders_submitted == 1
        assert len(gw.placed) == 1
        cycles = store.load_cycles()
        assert cycles[0]["orders_submitted"] == 1 and cycles[0]["signals_generated"] == 1
        execs = store.load_executions()
        assert execs[0]["status"] == "DRY_RUN" and execs[0]["notional"] == 500.0
        assert store.day_start_equity(today="2026-06-10") == 146000.0

    def test_first_cycle_writes_pretrade_baseline_snapshot(self, tmp_path):
        """评审发现 #4: 当日首循环必须先落盘前基准快照, 再交易(基准=交易前权益)。"""
        svc, store, _ = _service(tmp_path, displays=[_display()])

        svc.run_cycle()

        series = store.load_account_series(mode="dry_run")
        assert len(series) == 2  # 盘前基准 + 循环末快照

    def test_sell_signal_passes_with_position(self, tmp_path):
        pos = Position(account_id="t", ticker="601006.SH",
                       total_volume=100, available_volume=100, average_cost=5.0)
        svc, store, gw = _service(
            tmp_path, displays=[_display(direction=SignalDirection.SELL)],
            account=FakeAccount(positions=[pos]))

        summary = svc.run_cycle()

        assert summary.orders_submitted == 1
        assert gw.placed[0].direction.value == "SELL"


class TestFiltersAndBudget:
    def test_low_confidence_filtered(self, tmp_path):
        svc, store, _ = _service(tmp_path, displays=[_display(confidence=0.5)])
        summary = svc.run_cycle()
        assert summary.orders_submitted == 0 and summary.signals_generated == 1

    def test_max_orders_per_cycle_truncates(self, tmp_path):
        displays = [_display(symbol=f"60000{i}.SH") for i in range(5)]
        svc, store, _ = _service(
            tmp_path, displays=displays,
            config=AutoTradeConfig(mode="dry_run", max_orders_per_cycle=2))
        summary = svc.run_cycle()
        assert summary.orders_submitted + summary.orders_rejected == 2

    def test_daily_notional_cap_rejects(self, tmp_path):
        svc, store, _ = _service(
            tmp_path, displays=[_display()],
            config=AutoTradeConfig(mode="dry_run", daily_notional_cap=400.0))
        summary = svc.run_cycle()
        execs = store.load_executions()
        assert summary.orders_rejected == 1
        assert "预算" in execs[0]["reject_reason"]

    def test_same_day_same_key_dedup(self, tmp_path):
        svc, store, gw = _service(tmp_path, displays=[_display()])
        svc.run_cycle()
        summary2 = svc.run_cycle()
        assert summary2.orders_submitted == 0 and len(gw.placed) == 1

    def test_per_order_ceiling_default_rejects_large_order(self, tmp_path):
        """cap 抬高但 ceiling 默认 5000: 大单仍被硬顶拒绝(0611 安全值)。"""
        svc, store, gw = _service(
            tmp_path, displays=[_display(volume=1200)],  # notional ≈ 6000
            config=AutoTradeConfig(mode="dry_run", per_order_notional_cap=9000.0,
                                   daily_notional_cap=20000.0))
        summary = svc.run_cycle()
        assert summary.orders_rejected == 1 and not gw.placed

    def test_per_order_ceiling_raised_allows_large_order(self, tmp_path):
        """影子盘口径: ceiling 显式抬到 10000 后, cap 内大单放行。"""
        svc, store, gw = _service(
            tmp_path, displays=[_display(volume=1200)],  # notional ≈ 6000
            config=AutoTradeConfig(mode="dry_run", per_order_notional_cap=9000.0,
                                   per_order_notional_ceiling=10000.0,
                                   daily_notional_cap=20000.0))
        summary = svc.run_cycle()
        assert summary.orders_submitted == 1 and len(gw.placed) == 1

    def test_daily_loss_blocks_buys_allows_sells(self, tmp_path):
        pos = Position(account_id="t", ticker="600000.SH",
                       total_volume=100, available_volume=100, average_cost=5.0)
        store = TradingStore(str(tmp_path / "t.db"))
        store.save_account_snapshot(
            snapshot_time=NOW.replace(minute=31).isoformat(), mode="dry_run",
            total_asset=150000.0, available_cash=1e5, frozen_cash=0.0,
            market_value=5e4)
        gw = FakeTradeGateway()
        svc = AutoTradeAppService(
            signal_service=FakeSignalService([
                _display(symbol="601006.SH", direction=SignalDirection.BUY),
                _display(symbol="600000.SH", direction=SignalDirection.SELL),
            ]),
            quote_fetcher=FakeQuotes(), trade_gateway=gw,
            account_gateway=FakeAccount(total=146000.0, positions=[pos]),  # -2.67%
            store=store,
            audit=AuditService(SqliteAuditLogRepository(store.db)),
            config=AutoTradeConfig(mode="dry_run", daily_loss_limit_ratio=0.02),
            clock=lambda: NOW, sleep=lambda s: None)

        svc.run_cycle()

        execs = {e["symbol"]: e for e in store.load_executions()}
        assert "亏损" in execs["601006.SH"]["reject_reason"]
        assert execs["600000.SH"]["status"] == "DRY_RUN"


class TestSafetyHardening:
    def test_cash_cursor_decrements_within_cycle(self, tmp_path):
        """评审发现 #8: 同循环多笔买单需扣减资金游标, 不得共用陈旧快照。"""
        displays = [_display(symbol="600000.SH"), _display(symbol="601006.SH")]
        svc, store, gw = _service(tmp_path, displays=displays,
                                  account=FakeAccount(cash=600.0))

        summary = svc.run_cycle()

        # 报价 ask1=5.0 → 限价 5.0, notional 500, 需求 505; 600 只够第一单
        assert summary.orders_submitted == 1 and summary.orders_rejected == 1
        rejected = [e for e in store.load_executions() if e["status"] == "REJECTED"]
        assert "可用资金" in rejected[0]["reject_reason"]

    def test_per_order_exception_isolated_and_cycle_finalized(self, tmp_path):
        """评审发现 #3: 单笔异常不得炸穿循环; 快照与 finalize 必达。"""
        class BoomQuotes:
            def __init__(self):
                self.calls = 0
            def subscribe_first_tick(self, symbol, timeout=3.0):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("行情断连")
                return FakeQuotes()._q

        store = TradingStore(str(tmp_path / "t.db"))
        gw = FakeTradeGateway()
        svc = AutoTradeAppService(
            signal_service=FakeSignalService(
                [_display(symbol="600000.SH"), _display(symbol="601006.SH")]),
            quote_fetcher=BoomQuotes(), trade_gateway=gw,
            account_gateway=FakeAccount(), store=store,
            audit=AuditService(SqliteAuditLogRepository(store.db)),
            config=AutoTradeConfig(mode="dry_run"),
            clock=lambda: NOW, sleep=lambda s: None)

        summary = svc.run_cycle()

        assert summary.orders_failed == 1      # 第一单 FAILED 留痕
        assert summary.orders_submitted == 1   # 第二单照常执行
        cycles = store.load_cycles()
        assert cycles[0]["orders_failed"] == 1  # finalize 已执行

    def test_mode_gateway_mismatch_rejected_at_construction(self, tmp_path):
        """评审发现 #10: mode 标注必须与网关真实性一致, 失配应拒绝装配。"""
        import pytest
        store = TradingStore(str(tmp_path / "t.db"))
        with pytest.raises(ValueError, match="mode"):
            AutoTradeAppService(
                signal_service=FakeSignalService([]), quote_fetcher=FakeQuotes(),
                trade_gateway=FakeTradeGateway(),  # is_dry_run=True
                account_gateway=FakeAccount(), store=store,
                audit=AuditService(SqliteAuditLogRepository(store.db)),
                config=AutoTradeConfig(mode="live"),
                clock=lambda: NOW, sleep=lambda s: None)


class TestExecutionLifecycle:
    def test_timeout_cancels_order(self, tmp_path):
        gw = FakeTradeGateway(statuses=())  # 永远 ALIVE
        svc, store, _ = _service(
            tmp_path, displays=[_display()], trade_gw=gw,
            config=AutoTradeConfig(mode="dry_run", poll_timeout_seconds=0.0))

        svc.run_cycle()

        assert gw.canceled == ["gw-1"]
        assert store.load_executions()[0]["status"] == "TIMEOUT_CANCELED"

    def test_gate_rejection_recorded(self, tmp_path):
        svc, store, gw = _service(
            tmp_path, displays=[_display(symbol="300750.SZ")])
        summary = svc.run_cycle()
        assert summary.orders_rejected == 1 and not gw.placed
        assert "范围" in store.load_executions()[0]["reject_reason"]

    def test_place_failure_recorded_as_failed(self, tmp_path):
        from src.domain.trade.exceptions import OrderSubmitError

        class BoomGateway(FakeTradeGateway):
            def place_order(self, order):
                raise OrderSubmitError("QMT returned -1")

        svc, store, _ = _service(tmp_path, displays=[_display()],
                                 trade_gw=BoomGateway())
        summary = svc.run_cycle()
        assert summary.orders_failed == 1
        assert store.load_executions()[0]["status"] == "FAILED"

    def test_scan_data_health_error_persists_fault_snapshot_no_orders(self, tmp_path):
        """DataHealthError: note 留原因 + fault 快照落库 + 本周期零下单。"""
        class FaultingSignalService:
            def __init__(self):
                self.last_snapshot = None

            def scan(self, strategy_name, symbols):
                # 与 LiveSignalService 守卫路径一致: 先填 fault 快照再抛
                self.last_snapshot = _scan_snapshot(
                    data_health="fault", note="宇宙为空: 装配失败或配置错误",
                    gate_passed=False, positions=[], selection=[], targets=[],
                    total_asset=0.0)
                raise DataHealthError("宇宙为空: 装配失败或配置错误")

        store = TradingStore(str(tmp_path / "t.db"))
        gw = FakeTradeGateway()
        sig = FaultingSignalService()
        svc = AutoTradeAppService(
            signal_service=sig, quote_fetcher=FakeQuotes(),
            trade_gateway=gw, account_gateway=FakeAccount(),
            store=store, audit=AuditService(SqliteAuditLogRepository(store.db)),
            config=AutoTradeConfig(mode="dry_run"),
            clock=lambda: NOW, sleep=lambda s: None)

        summary = svc.run_cycle()

        assert summary.orders_submitted == 0 and gw.placed == []   # 零下单
        assert "宇宙为空" in store.load_cycles()[0]["note"]          # note 含原因
        rows = store.load_signal_snapshots()
        assert len(rows) == 1                                       # fault 快照落库
        assert rows[0]["cycle_id"] == summary.cycle_id
        assert rows[0]["data_health"] == "fault"
        assert rows[0]["gate_passed"] == 0
        assert json.loads(rows[0]["targets_json"]) == []
        assert sig.last_snapshot is None                            # 落库后清空

    def test_scan_exception_finalizes_cycle_with_note(self, tmp_path):
        class Boom:
            def scan(self, strategy_name, symbols):
                raise RuntimeError("qmt down")

        store = TradingStore(str(tmp_path / "t.db"))
        svc = AutoTradeAppService(
            signal_service=Boom(), quote_fetcher=FakeQuotes(),
            trade_gateway=FakeTradeGateway(), account_gateway=FakeAccount(),
            store=store, audit=AuditService(SqliteAuditLogRepository(store.db)),
            config=AutoTradeConfig(mode="dry_run"),
            clock=lambda: NOW, sleep=lambda s: None)

        summary = svc.run_cycle()

        assert summary.orders_submitted == 0
        assert "qmt down" in store.load_cycles()[0]["note"]


class TestScanSnapshotPersistence:
    def _svc(self, tmp_path, sig, *, store=None):
        store = store or TradingStore(str(tmp_path / "t.db"))
        gw = FakeTradeGateway()
        svc = AutoTradeAppService(
            signal_service=sig, quote_fetcher=FakeQuotes(),
            trade_gateway=gw, account_gateway=FakeAccount(),
            store=store, audit=AuditService(SqliteAuditLogRepository(store.db)),
            config=AutoTradeConfig(mode="dry_run"),
            clock=lambda: NOW, sleep=lambda s: None)
        return svc, store, gw

    def test_ok_snapshot_persisted_and_cycle_finalized(self, tmp_path):
        """截面 scan 成功: 快照按序列化约定落库 + last_snapshot 清空 + 正常 finalize。"""
        sig = SnapshotSignalService([_display()], _scan_snapshot())
        svc, store, gw = self._svc(tmp_path, sig)

        summary = svc.run_cycle()

        rows = store.load_signal_snapshots()
        assert len(rows) == 1
        row = rows[0]
        assert row["cycle_id"] == summary.cycle_id
        assert row["mode"] == "dry_run"
        assert row["snapshot_time"] == NOW.isoformat()
        assert row["fundamental_date"] == datetime(2026, 6, 9).isoformat()
        assert row["gate_passed"] == 1 and row["data_health"] == "ok"
        assert json.loads(row["selection_json"]) == ["601006.SH"]
        assert json.loads(row["positions_json"])[0]["total_volume"] == 100
        assert json.loads(row["targets_json"])[0]["direction"] == "BUY"
        assert sig.last_snapshot is None            # 防跨周期陈旧快照
        assert store.load_cycles()[0]["signals_generated"] == 1  # 正常 finalize
        assert summary.orders_submitted == 1        # 落库不影响执行链

    def test_bar_service_without_snapshot_attr_is_noop(self, tmp_path):
        """bar 路径(FakeSignalService 无 last_snapshot): 不落快照亦不报错。"""
        svc, store, _ = _service(tmp_path, displays=[_display()])
        svc.run_cycle()
        assert store.load_signal_snapshots() == []

    def test_snapshot_save_failure_does_not_kill_cycle(self, tmp_path, monkeypatch):
        """快照落库自身异常不得杀循环: 订单照常执行 + finalize 必达。"""
        sig = SnapshotSignalService([_display()], _scan_snapshot())
        svc, store, gw = self._svc(tmp_path, sig)

        def _boom(row):
            raise RuntimeError("disk full")

        monkeypatch.setattr(store, "save_signal_snapshot", _boom)

        summary = svc.run_cycle()

        assert summary.orders_submitted == 1
        assert store.load_cycles()[0]["orders_submitted"] == 1
