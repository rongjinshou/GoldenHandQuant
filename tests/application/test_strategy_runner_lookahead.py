from datetime import datetime

import pytest

from src.application.strategy_runner import CrossSectionalStrategyRunner, DayContext
from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.strategy.services.cross_section_builder import CrossSectionBuilder
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway


class _EmptyCS(CrossSectionalStrategy):
    @property
    def name(self) -> str:
        return "EmptyCS"

    def generate_cross_sectional_signals(self, universe, current_positions, current_date):
        return []


def _bar(sym, dt, close):
    return Bar(symbol=sym, timeframe=Timeframe.DAY_1, timestamp=dt,
               open=close, high=close * 1.02, low=close * 0.98, close=close, volume=1e6)


def test_cross_sectional_runner_feeds_only_past_bars_to_factor(monkeypatch):
    sym = "000001.SZ"
    t = datetime(2024, 6, 14)
    # 前 10 根平盘(close=10, 至 T-1), 第 11 根 T 跳到 99 → 若前视 return_5d 会≈8.9
    hist_bars = [_bar(sym, datetime(2024, 6, d), 10.0) for d in range(1, 11)]
    market = MockMarketGateway()
    market.add_bars(sym, [*hist_bars, _bar(sym, t, 99.0)])
    market.set_current_time(t)

    captured = {}

    def fake_build_cross_section(date, bars, registry, bar_history=None,
                                 precomputed_features=None, fundamental_date=None,
                                 status_registry=None):
        captured["snapshot_bar"] = bars[sym]
        captured["features"] = precomputed_features[sym]
        return []

    monkeypatch.setattr(CrossSectionBuilder, "build_cross_section",
                        staticmethod(fake_build_cross_section))

    runner = CrossSectionalStrategyRunner(
        strategy=_EmptyCS(), sizer=EqualWeightSizer(n_symbols=1),
        market_gateway=market, trade_gateway=MockTradeGateway(market, initial_capital=1_000_000),
        fundamental_registry=FundamentalRegistry(),
    )
    runner.evaluate(DayContext(current_time=t, symbols=[sym], base_timeframe=Timeframe.DAY_1))

    # 快照 bar 必须是 T-1(close=10), 非 T 日(close=99) — 否则前视
    assert captured["snapshot_bar"].close == 10.0
    # 技术特征(feature_engine)须为 as-of T-1: 平盘 → return_5d≈0; 若前视 T 跳涨则≈8.9
    assert captured["features"].get("return_5d", 0.0) == pytest.approx(0.0, abs=1e-12)


class _NoHistCS(CrossSectionalStrategy):
    @property
    def name(self) -> str:
        return "NoHistCS"

    @property
    def uses_bar_history(self) -> bool:
        return False

    def generate_cross_sectional_signals(self, universe, current_positions, current_date):
        return []


def test_cross_sectional_runner_skips_bar_history_when_strategy_opts_out(monkeypatch):
    # uses_bar_history=False 的策略 → runner 传 bar_history=None →
    # build_cross_section 跳过昂贵的逐股指标重算(MicroValue 等无需技术指标的策略避免 O(n²) 重算)。
    sym = "000001.SZ"
    t_minus_1 = datetime(2024, 6, 3)
    t = datetime(2024, 6, 4)
    market = MockMarketGateway()
    market.add_bars(sym, [_bar(sym, t_minus_1, 10.0), _bar(sym, t, 99.0)])
    market.set_current_time(t)

    captured = {}

    def fake_build_cross_section(date, bars, registry, bar_history=None,
                                 fundamental_date=None, status_registry=None):
        captured["history"] = bar_history
        return []

    monkeypatch.setattr(CrossSectionBuilder, "build_cross_section",
                        staticmethod(fake_build_cross_section))

    runner = CrossSectionalStrategyRunner(
        strategy=_NoHistCS(), sizer=EqualWeightSizer(n_symbols=1),
        market_gateway=market, trade_gateway=MockTradeGateway(market, initial_capital=1_000_000),
        fundamental_registry=FundamentalRegistry(),
    )
    runner.evaluate(DayContext(current_time=t, symbols=[sym], base_timeframe=Timeframe.DAY_1))

    assert captured["history"] is None  # 未传 bar 历史 → build_cross_section 跳过指标重算


def test_single_runner_feeds_only_past_bars_to_strategy():
    from src.application.strategy_runner import SingleStrategyRunner
    from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer
    from src.domain.strategy.services.base_strategy import BaseStrategy

    sym = "000001.SZ"
    t_minus_1 = datetime(2024, 6, 3)
    t = datetime(2024, 6, 4)
    market = MockMarketGateway()
    market.add_bars(sym, [_bar(sym, t_minus_1, 10.0), _bar(sym, t, 99.0)])
    market.set_current_time(t)

    captured = {}

    class _CaptureStrategy(BaseStrategy):
        @property
        def name(self): return "Capture"
        def generate_signals(self, market_data, current_positions):
            captured["data"] = market_data
            return []

    runner = SingleStrategyRunner(
        strategy=_CaptureStrategy(), sizer=FixedRatioSizer(ratio=0.2),
        market_gateway=market, trade_gateway=MockTradeGateway(market, initial_capital=1_000_000),
    )
    runner.evaluate(DayContext(current_time=t, symbols=[sym], base_timeframe=Timeframe.DAY_1))

    # 策略只应看到 T-1(close=10),不含 T 日(close=99)
    assert captured["data"][sym][-1].close == 10.0
    assert all(b.timestamp < t for b in captured["data"][sym])


class _CaptureUniverseCS(CrossSectionalStrategy):
    def __init__(self):
        self.seen = None

    @property
    def name(self) -> str:
        return "CaptureUniverse"

    @property
    def uses_bar_history(self) -> bool:
        return False

    def generate_cross_sectional_signals(self, universe, current_positions, current_date):
        self.seen = universe
        return []


def _fund(sym, dt, market_cap):
    from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
    return FundamentalSnapshot(
        symbol=sym, date=dt, name="测试", list_date=datetime(2020, 1, 1),
        market_cap=market_cap,
    )


def test_cross_sectional_runner_uses_t_minus_1_fundamentals():
    """confirmed-bug(2026-07-10 六西格玛体检 C1): market_cap/PE/PB 由 T 日收盘派生,
    T 日开盘执行时不可知 —— 回测曾精确取 T 日快照(前视)。技术腿早已 as-of T-1,
    唯基本面腿泄露; 实盘装配(alias T-1→now)本就是 T-1 口径, 修后两侧一致。"""
    sym = "000001.SZ"
    t_minus_1 = datetime(2024, 6, 3)
    t = datetime(2024, 6, 4)
    market = MockMarketGateway()
    market.add_bars(sym, [_bar(sym, t_minus_1, 10.0), _bar(sym, t, 11.0)])
    market.set_current_time(t)

    registry = FundamentalRegistry()
    registry.add(_fund(sym, t_minus_1, market_cap=100.0))   # T-1: 决策时可知
    registry.add(_fund(sym, t, market_cap=999.0))           # T: 收盘后才存在

    strategy = _CaptureUniverseCS()
    runner = CrossSectionalStrategyRunner(
        strategy=strategy, sizer=EqualWeightSizer(n_symbols=1),
        market_gateway=market,
        trade_gateway=MockTradeGateway(market, initial_capital=1_000_000),
        fundamental_registry=registry,
    )
    runner.evaluate(DayContext(current_time=t, symbols=[sym], base_timeframe=Timeframe.DAY_1))

    assert strategy.seen, "universe 不应为空"
    assert strategy.seen[0].market_cap == 100.0  # T-1 值, 而非 T 日收盘派生的 999


def test_fundamental_gap_falls_back_to_latest_available():
    """T-1 无快照(周末/缺口)时回退最近可得日 —— 精确匹配曾使宇宙为空,
    连带触发 sizer「空目标池 → 防御性清仓」的误伤。"""
    sym = "000001.SZ"
    t_minus_3 = datetime(2024, 5, 31)
    t_minus_1 = datetime(2024, 6, 3)
    t = datetime(2024, 6, 4)
    market = MockMarketGateway()
    market.add_bars(sym, [_bar(sym, t_minus_1, 10.0), _bar(sym, t, 11.0)])
    market.set_current_time(t)

    registry = FundamentalRegistry()
    registry.add(_fund(sym, t_minus_3, market_cap=88.0))  # 最近可得的是 T-3

    strategy = _CaptureUniverseCS()
    runner = CrossSectionalStrategyRunner(
        strategy=strategy, sizer=EqualWeightSizer(n_symbols=1),
        market_gateway=market,
        trade_gateway=MockTradeGateway(market, initial_capital=1_000_000),
        fundamental_registry=registry,
    )
    runner.evaluate(DayContext(current_time=t, symbols=[sym], base_timeframe=Timeframe.DAY_1))

    assert strategy.seen, "缺口日宇宙不应为空"
    assert strategy.seen[0].market_cap == 88.0
