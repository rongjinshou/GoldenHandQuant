from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.application.data_health import DataHealthError
from src.application.live_signal_service import LiveSignalService, SignalDisplay
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway


def _make_bars(symbol: str, prices: list[float]) -> list[Bar]:
    bars = []
    base = datetime(2026, 1, 1) - timedelta(days=len(prices))
    for i, p in enumerate(prices):
        bars.append(Bar(
            symbol=symbol, timeframe=Timeframe.DAY_1,
            timestamp=base + timedelta(days=i),
            open=p, high=p, low=p, close=p, volume=1000,
        ))
    return bars


class TestLiveSignalService:
    def _make_service(self) -> tuple[LiveSignalService, MagicMock, MagicMock, MagicMock]:
        market_gw = MagicMock()
        account_gw = MagicMock()
        trade_gw = MagicMock()

        account_gw.get_asset.return_value = Asset(
            account_id="test_acc", total_asset=1_000_000, available_cash=500_000,
        )
        account_gw.get_positions.return_value = []

        service = LiveSignalService(
            market_gateway=market_gw,
            account_gateway=account_gw,
            trade_gateway=trade_gw,
        )
        return service, market_gw, account_gw, trade_gw

    def test_scan_bar_strategy_should_return_signal_displays(self):
        service, market_gw, _, _ = self._make_service()
        market_gw.get_recent_bars.return_value = _make_bars("600000.SH", [10]*10 + [20])

        displays = service.scan(strategy_name="dual_ma", symbols=["600000.SH"])

        assert len(displays) == 1
        d = displays[0]
        assert d.symbol == "600000.SH"
        assert d.direction == SignalDirection.BUY
        assert d.current_price == 20.0
        assert d.suggested_volume > 0
        assert d.required_capital > 0
        assert "Golden Cross" in d.reason

    def test_scan_no_signals_should_return_empty(self):
        service, market_gw, _, _ = self._make_service()
        market_gw.get_recent_bars.return_value = _make_bars("600000.SH", [10]*20)

        displays = service.scan(strategy_name="dual_ma", symbols=["600000.SH"])

        assert len(displays) == 0

    def test_scan_insufficient_data_should_skip(self):
        service, market_gw, _, _ = self._make_service()
        market_gw.get_recent_bars.return_value = _make_bars("600000.SH", [10]*5)

        displays = service.scan(strategy_name="dual_ma", symbols=["600000.SH"])

        assert len(displays) == 0

    def test_scan_no_market_data_should_skip(self):
        service, market_gw, _, _ = self._make_service()
        market_gw.get_recent_bars.return_value = []

        displays = service.scan(strategy_name="dual_ma", symbols=["600000.SH"])

        assert len(displays) == 0

    def test_place_confirmed_orders_should_call_trade_gateway(self):
        service, _, _, trade_gw = self._make_service()
        trade_gw.place_order.return_value = "order_123"

        display = SignalDisplay(
            symbol="600000.SH", direction=SignalDirection.BUY,
            current_price=12.50, suggested_price=12.52,
            suggested_volume=500, required_capital=6260.0,
            reason="Golden Cross", strategy_name="DualMaStrategy",
            confidence_score=1.0,
        )

        results = service.place_confirmed_orders([display])

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].order_id == "order_123"
        trade_gw.place_order.assert_called_once()

    def test_place_confirmed_orders_failure_should_return_error(self):
        service, _, _, trade_gw = self._make_service()
        from src.domain.trade.exceptions import OrderSubmitError
        trade_gw.place_order.side_effect = OrderSubmitError("QMT error")

        display = SignalDisplay(
            symbol="600000.SH", direction=SignalDirection.BUY,
            current_price=12.50, suggested_price=12.52,
            suggested_volume=500, required_capital=6260.0,
            reason="test", strategy_name="test", confidence_score=1.0,
        )

        results = service.place_confirmed_orders([display])

        assert len(results) == 1
        assert results[0].success is False
        assert "QMT error" in results[0].error_message


_FIXED_TUESDAY = datetime(2024, 6, 11, 10, 0, 0)  # 周二(weekday()==1), 非 1/4 月


def _make_index_bars(closes: list[float], end_day: datetime = datetime(2024, 6, 11)) -> list[Bar]:
    """趋势闸指数 bars: 平走(全等收盘)时 MA20==close → pass_buy=True。"""
    start = end_day - timedelta(days=len(closes) - 1)
    return [Bar(
        symbol="000852.SH", timeframe=Timeframe.DAY_1,
        timestamp=start + timedelta(days=i),
        open=c, high=c, low=c, close=c, volume=1_000_000,
    ) for i, c in enumerate(closes)]


def _make_cs_market(symbols: list[str], index_closes: list[float] | None = None) -> MockMarketGateway:
    """截面 fixture 行情: 个股 7 根 bars(06-05..06-11) + 指数 bars(默认 25 根平走)。"""
    market = MockMarketGateway()
    for i, sym in enumerate(symbols):
        c = 10.0 + i
        market.add_bars(sym, [Bar(
            symbol=sym, timeframe=Timeframe.DAY_1, timestamp=datetime(2024, 6, d),
            open=c * 0.99, high=c * 1.02, low=c * 0.98, close=c,
            volume=1_000_000, prev_close=c * 0.99,
        ) for d in range(5, 12)])
    market.add_bars("000852.SH", _make_index_bars(index_closes or [5000.0] * 25))
    market.set_current_time(datetime(2024, 6, 11, 23, 59))
    return market


def _make_cs_registry(symbols: list[str]) -> FundamentalRegistry:
    registry = FundamentalRegistry()
    for i, sym in enumerate(symbols):
        registry.add(FundamentalSnapshot(
            symbol=sym, date=_FIXED_TUESDAY, name=f"Co{sym}",
            list_date=datetime(2000, 1, 1), market_cap=1e9 + i * 1e8,
            roe_ttm=0.15, ocf_ttm=1e8,
        ))
    return registry


def _make_account_gw(total: float = 1_000_000, cash: float = 1_000_000) -> MagicMock:
    account_gw = MagicMock()
    account_gw.get_asset.return_value = Asset(
        account_id="t", total_asset=total, available_cash=cash,
    )
    account_gw.get_positions.return_value = []
    return account_gw


def test_scan_cross_sectional_via_decision_core(monkeypatch):
    """截面 scan(micro_value) 经决策核心 CrossSectionalStrategyRunner 产 SignalDisplay。

    复用 test_strategy_runner_lookahead 的 fixture 模式: MockMarketGateway 装含
    fundamental 的截面 bars + FundamentalRegistry。micro_value 仅周二调仓 + 内部用
    datetime.now() → 冻结 now() 为固定周二(2024-06-11, 非 1/4 月)保证确定性。
    """
    from src.application import live_signal_service as lss

    fixed_now = _FIXED_TUESDAY

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(lss, "datetime", _FixedDatetime)

    symbols = ["000001.SZ", "000002.SZ", "000003.SZ"]
    market = _make_cs_market(symbols)
    registry = _make_cs_registry(symbols)

    trade = MockTradeGateway(market, initial_capital=1_000_000)
    account_gw = _make_account_gw()

    service = LiveSignalService(
        market_gateway=market, account_gateway=account_gw, trade_gateway=trade,
        sizer=EqualWeightSizer(n_symbols=len(symbols)),
        fundamental_registry=registry,
        min_fundamental_rows=1,  # fixture registry 仅 3 行
    )

    displays = service.scan(strategy_name="micro_value", symbols=symbols)

    assert len(displays) >= 1
    for d in displays:
        assert "决策核心" in d.reason
        assert d.confidence_score == 1.0
        assert d.suggested_volume > 0
        assert d.suggested_price > 0
        assert d.required_capital > 0
        assert d.direction == SignalDirection.BUY


def test_scan_cross_sectional_invokes_decision_core(monkeypatch):
    """截面 scan 路径必走 CrossSectionalStrategyRunner.evaluate(DayContext), 并把
    OrderTarget 映射为 SignalDisplay(reason 含 '决策核心', confidence==1.0)。

    用 fake runner 注入, 与策略内部细节解耦, 确定性验证分流+映射。
    """
    from src.application import strategy_runner as sr
    from src.application.strategy_runner import DayContext
    from src.domain.portfolio.entities.order_target import OrderTarget
    from src.domain.risk.services.system_risk_gate import SystemRiskGate
    from src.domain.trade.value_objects.order_direction import OrderDirection

    captured: dict = {}
    target = OrderTarget(
        symbol="000001.SZ", direction=OrderDirection.BUY,
        volume=300, price=12.0, strategy_name="MicroValueStrategy",
    )

    class _FakeRunner:
        def __init__(self, **kwargs):
            captured["init"] = kwargs
            self.system_gate = SystemRiskGate()

        def prime_index_data(self, index_bars, as_of):
            captured["primed"] = (len(index_bars), as_of)
            self.system_gate.set_index_data(index_bars)

        def evaluate(self, context):
            captured["context"] = context
            return [target], {"000001.SZ": 12.5}

    monkeypatch.setattr(sr, "CrossSectionalStrategyRunner", _FakeRunner)

    market = MagicMock()
    market.get_recent_bars.return_value = _make_index_bars([5000.0] * 25)
    account_gw = _make_account_gw()
    trade = MagicMock()
    trade.get_positions.return_value = []
    trade.get_asset.return_value = Asset(
        account_id="t", total_asset=1_000_000, available_cash=1_000_000,
    )

    class _RegistryStub:
        def get_all_at_date(self, date):
            return [object()]

    registry = _RegistryStub()  # sentinel(带守卫所需最小接口)

    service = LiveSignalService(
        market_gateway=market, account_gateway=account_gw, trade_gateway=trade,
        fundamental_registry=registry, min_fundamental_rows=1,
    )

    displays = service.scan(strategy_name="micro_value", symbols=["000001.SZ"])

    # 走了截面分流 → 构造了决策核心 runner, 注入了 fundamental_registry + DayContext
    assert captured["init"]["fundamental_registry"] is registry
    assert captured["primed"][0] == 25  # 守卫拉取的指数 bars 显式注入 runner, 不重拉
    assert isinstance(captured["context"], DayContext)
    assert captured["context"].symbols == ["000001.SZ"]
    assert captured["context"].base_timeframe == Timeframe.DAY_1
    # OrderTarget → SignalDisplay 映射
    assert len(displays) == 1
    d = displays[0]
    assert d.symbol == "000001.SZ"
    assert d.direction == SignalDirection.BUY
    assert d.current_price == 12.5      # prices.get(symbol)
    assert d.suggested_price == 12.0    # target.price
    assert d.suggested_volume == 300
    assert d.required_capital == round(12.0 * 300, 2)
    assert "决策核心" in d.reason
    assert d.strategy_name == "MicroValueStrategy"
    assert d.confidence_score == 1.0


def test_scan_signal_consistency_with_backtest_runner(monkeypatch):
    """信号一致性守门(R4): 实盘 LiveSignalService.scan 的目标组合 == 回测
    CrossSectionalStrategyRunner.evaluate 的目标组合(相同 market/fundamental/sizer/日期)。

    R3b 后实盘截面扫描内部即决策核心 → 给定相同输入, 实盘决策路径与回测决策路径逐位
    一致, 信号一致性是架构保证(非巧合)。这是回测/实盘归一重构(0628)的最终证明。
    """
    from src.application import live_signal_service as lss
    from src.application.strategy_runner import CrossSectionalStrategyRunner, DayContext
    from src.domain.strategy.registry import create_strategy

    fixed_now = _FIXED_TUESDAY

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(lss, "datetime", _FixedDatetime)

    symbols = ["000001.SZ", "000002.SZ", "000003.SZ"]
    # 25 根平走指数 bars: 两条路径趋势闸同为 pass_buy=True(语义与原 fail-open 不变)
    market = _make_cs_market(symbols)
    registry = _make_cs_registry(symbols)
    trade = MockTradeGateway(market, initial_capital=1_000_000)
    sizer = EqualWeightSizer(n_symbols=len(symbols))

    # 路径 A: 实盘决策路径 LiveSignalService.scan
    account_gw = MagicMock()
    account_gw.get_asset.return_value = trade.get_asset()
    account_gw.get_positions.return_value = []
    service = LiveSignalService(
        market_gateway=market, account_gateway=account_gw, trade_gateway=trade,
        sizer=sizer, fundamental_registry=registry,
        min_fundamental_rows=1,  # fixture registry 仅 3 行
    )
    displays = service.scan(strategy_name="micro_value", symbols=symbols)
    live = sorted(
        (d.symbol, d.direction.value, d.suggested_volume, round(d.suggested_price, 4))
        for d in displays
    )

    # 路径 B: 回测决策路径 CrossSectionalStrategyRunner.evaluate(相同输入)
    runner = CrossSectionalStrategyRunner(
        strategy=create_strategy("micro_value"), sizer=sizer,
        market_gateway=market, trade_gateway=trade, fundamental_registry=registry,
    )
    targets, _ = runner.evaluate(DayContext(
        current_time=fixed_now, symbols=symbols, base_timeframe=Timeframe.DAY_1,
    ))
    bt = sorted(
        (t.symbol, t.direction.value, t.volume, round(t.price, 4)) for t in targets
    )

    assert live == bt, f"信号不一致: 实盘 {live} != 回测 {bt}"
    assert len(live) >= 1  # 确实产了非空目标组合


# ---- B2: scan 数据健康守卫 + ScanSnapshot 决策快照(0626 阶段1 DD-4/DD-7) ----


def _make_guard_service(
    market, trade, registry, *, min_rows: int = 1, params: dict | None = None,
    clock=None,
) -> LiveSignalService:
    return LiveSignalService(
        market_gateway=market, account_gateway=_make_account_gw(), trade_gateway=trade,
        sizer=EqualWeightSizer(n_symbols=3), fundamental_registry=registry,
        strategy_params=params, min_fundamental_rows=min_rows,
        clock=clock or (lambda: _FIXED_TUESDAY),
    )


def test_scan_empty_universe_raises_and_snapshots_fault():
    service = _make_guard_service(MagicMock(), MagicMock(), FundamentalRegistry())

    with pytest.raises(DataHealthError):
        service.scan(strategy_name="micro_value", symbols=[])

    snap = service.last_snapshot
    assert snap is not None
    assert snap.data_health == "fault"
    assert "宇宙" in snap.note
    assert snap.targets == [] and snap.selection == []
    assert snap.snapshot_time == _FIXED_TUESDAY


def test_scan_insufficient_fundamental_rows_raises():
    symbols = ["000001.SZ", "000002.SZ", "000003.SZ"]
    market = _make_cs_market(symbols)
    registry = _make_cs_registry(symbols[:2])  # 只 2 行 < min 3
    trade = MockTradeGateway(market, initial_capital=1_000_000)
    service = _make_guard_service(market, trade, registry, min_rows=3)

    with pytest.raises(DataHealthError):
        service.scan(strategy_name="micro_value", symbols=symbols)

    snap = service.last_snapshot
    assert snap.data_health == "fault"
    assert snap.fundamental_rows == 2
    assert snap.targets == [] and snap.selection == []


def test_scan_insufficient_index_bars_raises():
    symbols = ["000001.SZ", "000002.SZ", "000003.SZ"]
    market = _make_cs_market(symbols, index_closes=[5000.0] * 10)  # < 20 根
    registry = _make_cs_registry(symbols)
    trade = MagicMock()
    trade.get_positions.return_value = [Position(
        account_id="t", ticker="000001.SZ",
        total_volume=1000, available_volume=1000, average_cost=10.0,
    )]
    trade.get_asset.return_value = Asset(
        account_id="t", total_asset=1_000_000, available_cash=990_000,
    )
    service = _make_guard_service(market, trade, registry)

    with pytest.raises(DataHealthError):
        service.scan(strategy_name="micro_value", symbols=symbols)

    # 有持仓也不产生任何 SELL: 数据故障 abort ≠ 清仓
    snap = service.last_snapshot
    assert snap.data_health == "fault"
    assert snap.index_bars_count == 10
    assert snap.targets == [] and snap.selection == []


def test_scan_stock_bars_all_empty_raises_not_liquidates():
    """指数可得但个股行情全断(部分断连) → fault abort, 绝不落入清仓分支(K1 红线)。"""
    symbols = ["000001.SZ", "000002.SZ", "000003.SZ"]
    market = MockMarketGateway()   # 只装指数, 个股 bars 全空
    market.add_bars("000852.SH", _make_index_bars([5000.0] * 25))
    market.set_current_time(datetime(2024, 6, 11, 23, 59))
    registry = _make_cs_registry(symbols)
    trade = MagicMock()
    trade.get_positions.return_value = [Position(
        account_id="t", ticker="000001.SZ",
        total_volume=1000, available_volume=1000, average_cost=10.0,
    )]
    trade.get_asset.return_value = Asset(
        account_id="t", total_asset=1_000_000, available_cash=990_000,
    )
    service = _make_guard_service(market, trade, registry)

    with pytest.raises(DataHealthError):
        service.scan(strategy_name="micro_value", symbols=symbols)

    snap = service.last_snapshot
    assert snap.data_health == "fault"
    assert "个股行情" in snap.note
    assert snap.targets == [] and snap.selection == []


def test_scan_gate_blocked_liquidation_allowed():
    """指数末根 < MA20 且数据完好 → 合法清仓路径照常放行(设计内行为, 非数据故障)。"""
    symbols = ["000001.SZ", "000002.SZ", "000003.SZ"]
    market = _make_cs_market(symbols, index_closes=[5000.0] * 24 + [4000.0])
    registry = _make_cs_registry(symbols)
    trade = MagicMock()
    trade.get_positions.return_value = [Position(
        account_id="t", ticker="000001.SZ",
        total_volume=1000, available_volume=1000, average_cost=10.0,
    )]
    trade.get_asset.return_value = Asset(
        account_id="t", total_asset=1_000_000, available_cash=990_000,
    )
    service = _make_guard_service(market, trade, registry)

    displays = service.scan(strategy_name="micro_value", symbols=symbols)

    assert len(displays) >= 1
    assert all(d.direction == SignalDirection.SELL for d in displays)
    snap = service.last_snapshot
    assert snap.gate_passed is False
    assert snap.data_health == "ok"
    assert snap.selection == []  # 闸阻断 → 无 BUY 目标池


def test_scan_snapshot_captures_inputs_and_outputs():
    symbols = ["000001.SZ", "000002.SZ", "000003.SZ"]
    market = _make_cs_market(symbols)
    registry = _make_cs_registry(symbols)
    trade = MockTradeGateway(market, initial_capital=1_000_000)
    service = _make_guard_service(market, trade, registry)

    displays = service.scan(strategy_name="micro_value", symbols=symbols)

    snap = service.last_snapshot
    assert snap.data_health == "ok" and snap.note == ""
    assert snap.snapshot_time == _FIXED_TUESDAY
    assert snap.strategy == "micro_value"
    assert snap.gate_passed is True
    assert snap.fundamental_rows == 3
    assert snap.index_bars_count == 25
    # assembly_meta 未注入 → 回退 len(symbols)/0
    assert snap.universe_size == 3 and snap.filtered_size == 3
    assert snap.staleness_days == 0
    assert snap.positions == []  # MockTradeGateway 初始空仓
    assert snap.total_asset == 1_000_000
    assert snap.selection == sorted(
        d.symbol for d in displays if d.direction == SignalDirection.BUY
    )
    assert len(snap.targets) == len(displays) >= 1
    assert {(t["symbol"], t["direction"], t["volume"]) for t in snap.targets} == {
        (d.symbol, d.direction.value, d.suggested_volume) for d in displays
    }


def test_strategy_params_control_top_n():
    symbols = ["000001.SZ", "000002.SZ", "000003.SZ"]
    market = _make_cs_market(symbols)
    registry = _make_cs_registry(symbols)
    trade = MockTradeGateway(market, initial_capital=1_000_000)
    service = _make_guard_service(market, trade, registry, params={"top_n": 2})

    service.scan(strategy_name="micro_value", symbols=symbols)

    snap = service.last_snapshot
    assert len(snap.selection) == 2
    assert snap.selection == ["000001.SZ", "000002.SZ"]  # 市值升序前 2


def test_clock_injection():
    """clock 注入固定周二 → 与真实 datetime.now() 无关地复现选股(比对脚本 DD-8 前提)。

    未注入时钟时 registry 在真实今天无行, 守卫必 abort → scan 正常产出即证明
    决策全程用的是注入时钟。
    """
    symbols = ["000001.SZ", "000002.SZ", "000003.SZ"]
    market = _make_cs_market(symbols)
    registry = _make_cs_registry(symbols)
    trade = MockTradeGateway(market, initial_capital=1_000_000)
    service = _make_guard_service(market, trade, registry, clock=lambda: _FIXED_TUESDAY)

    displays = service.scan(strategy_name="micro_value", symbols=symbols)

    snap = service.last_snapshot
    assert snap.snapshot_time == _FIXED_TUESDAY
    assert snap.selection == symbols  # 周二调仓日全 3 只入选(top_n 默认 9)
    assert len(displays) == 3
