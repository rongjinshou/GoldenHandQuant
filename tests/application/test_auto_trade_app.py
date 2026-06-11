"""AutoTradeAppService 测试 — 全链路 dry-run、各闸拒单、预算/亏损/去重/超时撤单。"""
from datetime import datetime

from src.application.auto_trade_app import AutoTradeAppService, AutoTradeConfig
from src.application.live_signal_service import SignalDisplay
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
