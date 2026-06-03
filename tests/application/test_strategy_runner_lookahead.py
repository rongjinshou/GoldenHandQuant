from datetime import datetime

from src.application.strategy_runner import CrossSectionalStrategyRunner, DayContext
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway
from src.infrastructure.ml_engine.feature_pipeline import FeaturePipeline


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
    t_minus_1 = datetime(2024, 6, 3)
    t = datetime(2024, 6, 4)
    market = MockMarketGateway()
    market.add_bars(sym, [_bar(sym, t_minus_1, 10.0), _bar(sym, t, 99.0)])
    market.set_current_time(t)

    captured = {}

    def fake_build_cross_section(date, bars, registry, bar_history=None):
        captured["snapshot_bar"] = bars[sym]
        captured["history"] = bar_history[sym]
        return []

    monkeypatch.setattr(FeaturePipeline, "build_cross_section",
                        staticmethod(fake_build_cross_section))

    runner = CrossSectionalStrategyRunner(
        strategy=_EmptyCS(), sizer=EqualWeightSizer(n_symbols=1),
        market_gateway=market, trade_gateway=MockTradeGateway(market, initial_capital=1_000_000),
        fundamental_registry=FundamentalRegistry(),
    )
    runner.evaluate(DayContext(current_time=t, symbols=[sym], base_timeframe=Timeframe.DAY_1))

    # The factor must see T-1 data (close=10), not T-day (close=99) -- otherwise it's lookahead
    assert captured["snapshot_bar"].close == 10.0
    assert captured["history"][-1].close == 10.0
    assert all(b.timestamp < t for b in captured["history"])


def test_single_runner_feeds_only_past_bars_to_strategy():
    from src.application.strategy_runner import SingleStrategyRunner
    from src.domain.strategy.services.base_strategy import BaseStrategy
    from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer

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
