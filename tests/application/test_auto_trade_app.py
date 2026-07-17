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

    def get_quotes(self, symbols):
        """债D4: run_cycle 循环前批量拉取, 替代逐候选 subscribe_first_tick。"""
        return {s: self._q for s in symbols}


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
        # 券商单号唯一(真实语义, H1 rename 依赖): 首单保持原值兼容既有断言, 后续递增
        if len(self.placed) == 1:
            return self._place_id
        return f"{self._place_id}-{len(self.placed)}"

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


def _service(tmp_path, *, displays, trade_gw=None, account=None, config=None,
             quotes=None):
    store = TradingStore(str(tmp_path / "t.db"))
    gw = trade_gw if trade_gw is not None else FakeTradeGateway()
    svc = AutoTradeAppService(
        signal_service=FakeSignalService(displays),
        quote_fetcher=quotes if quotes is not None else FakeQuotes(),
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


class _StQuotes(FakeQuotes):
    """带实时名称能力的报价替身(0704 DD-3): 模拟当日刚戴帽。"""

    def get_instrument_name(self, symbol):
        return "ST 测试"


class TestRealtimeStGate:
    def test_buy_rejected_when_realtime_name_is_st(self, tmp_path):
        svc, store, gw = _service(tmp_path, displays=[_display()], quotes=_StQuotes())

        summary = svc.run_cycle()

        assert summary.orders_rejected == 1 and gw.placed == []
        recs = store.load_executions()
        assert "风险警示" in recs[0]["reject_reason"]

    def test_sell_passes_even_when_name_is_st(self, tmp_path):
        pos = Position(account_id="t", ticker="601006.SH",
                       total_volume=100, available_volume=100, average_cost=5.0)
        svc, _, gw = _service(
            tmp_path, displays=[_display(direction=SignalDirection.SELL)],
            account=FakeAccount(positions=[pos]), quotes=_StQuotes())

        summary = svc.run_cycle()

        assert summary.orders_submitted == 1  # 退出持仓不被自身 ST 阻断
        assert gw.placed[0].direction.value == "SELL"

    def test_fetcher_without_name_capability_passes(self, tmp_path):
        """FakeQuotes 无 get_instrument_name → 名称不可得 → 放行(既有行为回归)。"""
        svc, _, gw = _service(tmp_path, displays=[_display()])

        summary = svc.run_cycle()

        assert summary.orders_submitted == 1 and len(gw.placed) == 1


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
        """评审发现 #3: 单笔异常不得炸穿循环; 快照与 finalize 必达。

        债D4批量拉取行情后, 报价不再是逐候选故障点; 改用下单网关在第一单
        抛出非 OrderSubmitError 异常(如断线), 验证 _execute_one 仍逐单隔离。
        """
        class BoomGateway(FakeTradeGateway):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def place_order(self, order):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("下单网关断连")
                return super().place_order(order)

        store = TradingStore(str(tmp_path / "t.db"))
        gw = BoomGateway()
        svc = AutoTradeAppService(
            signal_service=FakeSignalService(
                [_display(symbol="600000.SH"), _display(symbol="601006.SH")]),
            quote_fetcher=FakeQuotes(), trade_gateway=gw,
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


class ExplodingAudit:
    """place_order 动作时抛异常的审计替身(模拟下单后审计写库故障)。"""

    def __init__(self, real):
        self._real = real

    def log_action(self, **kwargs):
        if kwargs.get("action") == "place_order":
            raise RuntimeError("database is locked")
        return self._real.log_action(**kwargs)


class TestAuditFailureIsolation:
    def test_audit_failure_after_place_does_not_mark_order_failed(self, tmp_path):
        """confirmed-bug(2026-07-10 六西格玛体检 L10): place_order 成功后审计写库
        异常曾沿 _execute_one 的 except 把真单误标 FAILED、并跳过撤单轮询——
        账本与券商真实状态背离。审计是观测面, 不得改写交易控制流。"""
        store = TradingStore(str(tmp_path / "t.db"))
        gw = FakeTradeGateway()
        svc = AutoTradeAppService(
            signal_service=FakeSignalService([_display()]),
            quote_fetcher=FakeQuotes(),
            trade_gateway=gw,
            account_gateway=FakeAccount(),
            store=store,
            audit=ExplodingAudit(AuditService(SqliteAuditLogRepository(store.db))),
            config=AutoTradeConfig(mode="dry_run"),
            clock=lambda: NOW,
            sleep=lambda s: None,
        )

        summary = svc.run_cycle()

        execs = store.load_executions()
        assert len(gw.placed) == 1
        assert execs[0]["status"] == "DRY_RUN"  # 真实终态, 而非 FAILED
        assert summary.orders_submitted == 1


class SpyGateway(FakeTradeGateway):
    """place_order 时回查 store 的网关替身（钉死「先落账后下单」事务顺序）。"""

    def __init__(self, store, **kw):
        super().__init__(**kw)
        self._spy_store = store
        self.pending_seen_at_place: list[dict] = []

    def place_order(self, order):
        rows = [r for r in self._spy_store.load_executions()
                if r["symbol"] == order.ticker and r["status"] == "PENDING"]
        self.pending_seen_at_place.extend(rows)
        return super().place_order(order)


class TestIdempotencyH1:
    """H1 下单幂等（2026-07-10 六西格玛体检, 决策项 Q1 获批）。

    旧时序: place_order → (最长30s轮询) → save_execution。窗口内崩溃 =
    券商有真单而账本无行, 重启后当日去重查不到 → 重复下单。
    新时序: 预算闸通过后先落 PENDING 行, place 后改写真单号, 终态再覆盖;
    run_cycle 开头对账非终态残留并告警。
    """

    def test_pending_row_persisted_before_place_order(self, tmp_path):
        store = TradingStore(str(tmp_path / "t.db"))
        gw = SpyGateway(store)
        svc = AutoTradeAppService(
            signal_service=FakeSignalService([_display()]),
            quote_fetcher=FakeQuotes(), trade_gateway=gw,
            account_gateway=FakeAccount(), store=store,
            audit=AuditService(SqliteAuditLogRepository(store.db)),
            config=AutoTradeConfig(mode="dry_run"),
            clock=lambda: NOW, sleep=lambda s: None,
        )

        svc.run_cycle()

        assert len(gw.pending_seen_at_place) == 1  # 下单那一刻账本里已有 PENDING
        assert gw.pending_seen_at_place[0]["symbol"] == "601006.SH"
        # 终态覆盖 PENDING(order_id 已换成真单号)
        execs = store.load_executions()
        assert len(execs) == 1
        assert execs[0]["status"] == "DRY_RUN"
        assert execs[0]["order_id"] == "gw-1"

    def test_stale_pending_dedupes_next_cycle_and_alerts(self, tmp_path):
        """崩溃残留(PENDING 非终态)必须: ① 占当日去重(不重复下单) ② 对账告警。"""
        store = TradingStore(str(tmp_path / "t.db"))
        store.save_execution({
            "order_id": "gw-orphan", "cycle_id": "crashed-cycle",
            "mode": "dry_run", "symbol": "601006.SH", "direction": "BUY",
            "signal_price": 5.0, "exec_price": 5.0, "volume": 100,
            "notional": 500.0, "status": "PENDING", "reject_reason": None,
            "strategy_name": "dual_ma", "confidence": 0.9,
            "submitted_at": NOW.isoformat(), "final_status_at": None,
            "status_trail": "[]",
        })
        gw = FakeTradeGateway()
        svc = AutoTradeAppService(
            signal_service=FakeSignalService([_display()]),  # 同标的同方向
            quote_fetcher=FakeQuotes(), trade_gateway=gw,
            account_gateway=FakeAccount(), store=store,
            audit=AuditService(SqliteAuditLogRepository(store.db)),
            config=AutoTradeConfig(mode="dry_run"),
            clock=lambda: NOW, sleep=lambda s: None,
        )

        summary = svc.run_cycle()

        assert len(gw.placed) == 0          # 残留 PENDING 占去重 → 不再下单
        assert summary.orders_submitted == 0
        audits = store.db.execute(
            "SELECT action FROM audit_logs WHERE action='reconcile_stale_execution'"
        ).fetchall()
        assert len(audits) == 1             # 对账告警已留痕

    def test_poll_exception_after_submit_keeps_budget_occupancy(self, tmp_path, monkeypatch):
        """place 已发出后轮询异常(进程未死): 不得标 FAILED(不占预算/去重) →
        改标 FAILED_AFTER_SUBMIT(占用), 防同标的立刻追单重复。"""
        store = TradingStore(str(tmp_path / "t.db"))
        gw = FakeTradeGateway()
        svc = AutoTradeAppService(
            signal_service=FakeSignalService([_display()]),
            quote_fetcher=FakeQuotes(), trade_gateway=gw,
            account_gateway=FakeAccount(), store=store,
            audit=AuditService(SqliteAuditLogRepository(store.db)),
            config=AutoTradeConfig(mode="dry_run"),
            clock=lambda: NOW, sleep=lambda s: None,
        )
        monkeypatch.setattr(svc, "_poll",
                            lambda oid: (_ for _ in ()).throw(RuntimeError("poll boom")))

        svc.run_cycle()

        execs = store.load_executions()
        assert execs[0]["status"] == "FAILED_AFTER_SUBMIT"
        assert store.today_traded_keys(today="2026-06-10", mode="dry_run") == {"601006.SH:BUY"}


class TestRiskPolicyGateM5:
    """M5 正式风控接线（2026-07-10 六西格玛体检, 决策项 Q2 获批）。

    PositionLimit(单票≤30%)/TotalPosition(总仓≤80%)此前生产零实例化——
    实盘仓位约束只剩 sizer 目标权重 + notional cap。接入执行期硬闸:
    无状态、每单即时计算, --once 与守护模式同等有效。
    """

    def _svc(self, tmp_path, *, displays, positions=(), total=146000.0,
             cash=100000.0):
        store = TradingStore(str(tmp_path / "t.db"))
        gw = FakeTradeGateway()
        svc = AutoTradeAppService(
            signal_service=FakeSignalService(displays),
            quote_fetcher=FakeQuotes(), trade_gateway=gw,
            account_gateway=FakeAccount(cash=cash, total=total,
                                        positions=list(positions)),
            store=store,
            audit=AuditService(SqliteAuditLogRepository(store.db)),
            config=AutoTradeConfig(mode="dry_run", per_order_notional_cap=99999,
                                   per_order_notional_ceiling=99999,
                                   daily_notional_cap=999999),
            clock=lambda: NOW, sleep=lambda s: None,
        )
        return svc, store, gw

    def test_buy_exceeding_single_position_limit_rejected(self, tmp_path):
        # 总资产 146000 → 单票上限 30% = 43800; 已持仓成本市值 40000,
        # 再买 1000 股×5.0=5000 → 45000 > 43800 拒
        pos = Position(account_id="t", ticker="601006.SH",
                       total_volume=8000, available_volume=8000, average_cost=5.0)
        svc, store, gw = self._svc(
            tmp_path, displays=[_display(volume=1000)], positions=[pos])

        summary = svc.run_cycle()

        assert summary.orders_rejected == 1
        assert len(gw.placed) == 0
        execs = store.load_executions()
        assert "Position limit" in execs[0]["reject_reason"]

    def test_buy_within_single_position_limit_passes(self, tmp_path):
        pos = Position(account_id="t", ticker="601006.SH",
                       total_volume=8000, available_volume=8000, average_cost=5.0)
        svc, _, gw = self._svc(
            tmp_path, displays=[_display(volume=100)], positions=[pos])

        summary = svc.run_cycle()

        assert summary.orders_submitted == 1
        assert len(gw.placed) == 1

    def test_buy_exceeding_total_position_limit_rejected(self, tmp_path):
        # 总仓上限 80% = 116800; 其他持仓按报价 last=5.0 估值 23300 股 = 116500,
        # 再买 100 股×5.0=500 → 117000 > 116800 拒(单票 601006 本身不超 30%)
        other = Position(account_id="t", ticker="605589.SH",
                         total_volume=23300, available_volume=23300, average_cost=5.0)
        svc, store, gw = self._svc(
            tmp_path, displays=[_display(volume=100)], positions=[other])

        summary = svc.run_cycle()

        assert summary.orders_rejected == 1
        assert len(gw.placed) == 0
        execs = store.load_executions()
        assert "Total position" in execs[0]["reject_reason"]

    def test_sell_not_limited_by_position_caps(self, tmp_path):
        # 超总仓状态下卖出必须放行(减仓是风控希望发生的方向)
        pos = Position(account_id="t", ticker="601006.SH",
                       total_volume=30000, available_volume=30000, average_cost=5.0)
        svc, _, gw = self._svc(
            tmp_path,
            displays=[_display(direction=SignalDirection.SELL, volume=100)],
            positions=[pos])

        summary = svc.run_cycle()

        assert summary.orders_submitted == 1
        assert len(gw.placed) == 1


def _breaker_service(tmp_path, store, *, displays, total=146000.0,
                     positions=(), now=None):
    """带熔断器的服务工厂（T6）。报价时间戳跟随注入时钟(过新鲜度闸)。"""
    from src.domain.risk.services.circuit_breaker import CircuitBreaker

    effective_now = now or NOW
    quote = Quote(symbol="601006.SH", last=5.0, bid1=4.99, ask1=5.0,
                  prev_close=5.0, timestamp=effective_now)
    gw = FakeTradeGateway()
    svc = AutoTradeAppService(
        signal_service=FakeSignalService(displays),
        quote_fetcher=FakeQuotes(quote), trade_gateway=gw,
        account_gateway=FakeAccount(total=total, positions=list(positions)),
        store=store,
        audit=AuditService(SqliteAuditLogRepository(store.db)),
        config=AutoTradeConfig(mode="dry_run"),
        clock=lambda: effective_now,
        sleep=lambda s: None,
        circuit_breaker=CircuitBreaker(max_daily_loss=0.03),
    )
    return svc, gw


class TestCircuitBreakerT6:
    """熔断器持久化+接线（2026-07-11 六西格玛 T6, M5 遗留专项）。

    语义: 熔断保护账户而非进程。当日亏损 >3% → TRIGGERED(禁全部, 含卖出,
    与 2% 软禁买构成递进防线) → 次日 COOLDOWN(仅卖) → 再次日 NORMAL。
    状态入 trading.db, --once 每次新进程也能续上状态机。
    """

    def _seed_baseline(self, store, day: str, equity: float):
        store.save_account_snapshot(
            snapshot_time=f"{day}T09:00:00", mode="dry_run",
            total_asset=equity, available_cash=equity, frozen_cash=0.0,
            market_value=0.0)

    def test_daily_loss_triggers_and_persists(self, tmp_path):
        store = TradingStore(str(tmp_path / "t.db"))
        self._seed_baseline(store, "2026-06-10", 152000.0)  # 盘前基准
        # 当前资产 146000 → 当日 -3.95% > 3% → 熔断; SELL 候选证明"禁全部"
        pos = Position(account_id="t", ticker="601006.SH",
                       total_volume=100, available_volume=100, average_cost=5.0)
        svc, gw = _breaker_service(
            tmp_path, store,
            displays=[_display(direction=SignalDirection.SELL)],
            positions=[pos])

        summary = svc.run_cycle()

        assert len(gw.placed) == 0
        assert summary.orders_rejected == 1
        execs = store.load_executions()
        assert "熔断" in execs[0]["reject_reason"]
        saved, last_reset = store.load_breaker_state(mode="dry_run")
        assert saved is not None and saved.blocks_all_trading
        assert last_reset == "2026-06-10"

    def test_triggered_state_survives_process_restart(self, tmp_path):
        store = TradingStore(str(tmp_path / "t.db"))
        self._seed_baseline(store, "2026-06-10", 152000.0)
        svc1, _ = _breaker_service(tmp_path, store, displays=[_display()])
        svc1.run_cycle()  # 触发并落库

        # "重启": 全新 service + 全新 CircuitBreaker 实例, 同一 store
        svc2, gw2 = _breaker_service(tmp_path, store, displays=[_display()])
        summary2 = svc2.run_cycle()

        assert len(gw2.placed) == 0            # 恢复 TRIGGERED → 依然全拒
        assert summary2.orders_rejected == 1

    def test_next_day_cooldown_allows_sell_only(self, tmp_path):
        from datetime import datetime

        store = TradingStore(str(tmp_path / "t.db"))
        self._seed_baseline(store, "2026-06-10", 152000.0)
        svc1, _ = _breaker_service(tmp_path, store, displays=[_display()])
        svc1.run_cycle()  # D0 触发

        day2 = datetime(2026, 6, 11, 9, 35)    # 周四
        pos = Position(account_id="t", ticker="601006.SH",
                       total_volume=100, available_volume=100, average_cost=5.0)
        # D1: 买单被拒(冷却仅卖)
        svc_buy, gw_buy = _breaker_service(
            tmp_path, store, displays=[_display()], now=day2)
        svc_buy.run_cycle()
        assert len(gw_buy.placed) == 0

        # D1: 卖单放行
        svc_sell, gw_sell = _breaker_service(
            tmp_path, store,
            displays=[_display(direction=SignalDirection.SELL)],
            positions=[pos], now=day2)
        summary = svc_sell.run_cycle()
        assert len(gw_sell.placed) == 1
        assert summary.orders_submitted == 1

    def test_third_day_recovers_normal(self, tmp_path):
        from datetime import datetime

        store = TradingStore(str(tmp_path / "t.db"))
        self._seed_baseline(store, "2026-06-10", 152000.0)
        svc1, _ = _breaker_service(tmp_path, store, displays=[_display()])
        svc1.run_cycle()                                        # D0 触发
        svc2, _ = _breaker_service(tmp_path, store, displays=[_display()],
                                   now=datetime(2026, 6, 11, 9, 35))
        svc2.run_cycle()                                        # D1 冷却

        svc3, gw3 = _breaker_service(tmp_path, store, displays=[_display()],
                                     now=datetime(2026, 6, 12, 9, 35))
        summary3 = svc3.run_cycle()                             # D2 恢复

        assert len(gw3.placed) == 1
        assert summary3.orders_submitted == 1
