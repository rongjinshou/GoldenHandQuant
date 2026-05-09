from datetime import datetime

from src.domain.account.entities.position import Position
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.quality_factor import ROEQualityFactor
from src.domain.strategy.factors.value_factor import PBValueFactor
from src.domain.strategy.services.strategies.multi_factor_strategy import MultiFactorStrategy
from src.domain.strategy.value_objects.signal_direction import SignalDirection


def _make_snapshot(symbol: str, pb: float, roe: float) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 6, 15),
        open=10, high=10, low=10, close=10, volume=1000,
        name=f"stock_{symbol}", list_date=datetime(2020, 1, 1),
        market_cap=1e10, pb_ratio=pb, roe_ttm=roe,
    )


class TestMultiFactorStrategy:
    def test_generate_signals_selects_top_n(self):
        strategy = MultiFactorStrategy(
            factors=[PBValueFactor(), ROEQualityFactor()],
            weights=[0.5, 0.5],
            top_n=2,
        )
        universe = [
            _make_snapshot("A", pb=1.0, roe=0.20),
            _make_snapshot("B", pb=2.0, roe=0.15),
            _make_snapshot("C", pb=5.0, roe=0.05),
        ]

        signals = strategy.generate_cross_sectional_signals(
            universe=universe,
            current_positions=[],
            current_date=datetime(2024, 6, 15),
        )

        assert len(signals) == 2
        symbols = {s.symbol for s in signals}
        assert "A" in symbols
        assert "B" in symbols
        for s in signals:
            assert s.direction == SignalDirection.BUY
            assert s.strategy_name == "MultiFactorStrategy"

    def test_generate_signals_sells_dropped_positions(self):
        strategy = MultiFactorStrategy(
            factors=[PBValueFactor()],
            weights=[1.0],
            top_n=2,
        )
        universe = [
            _make_snapshot("A", pb=1.0, roe=0.15),
            _make_snapshot("B", pb=2.0, roe=0.15),
            _make_snapshot("C", pb=3.0, roe=0.15),
        ]
        positions = [
            Position(account_id="acc", ticker="A", total_volume=100, available_volume=100),
            Position(account_id="acc", ticker="C", total_volume=100, available_volume=100),
        ]

        signals = strategy.generate_cross_sectional_signals(
            universe=universe,
            current_positions=positions,
            current_date=datetime(2024, 6, 15),
        )

        buy_symbols = {s.symbol for s in signals if s.direction == SignalDirection.BUY}
        sell_symbols = {s.symbol for s in signals if s.direction == SignalDirection.SELL}
        assert len(buy_symbols) >= 1
        assert "C" in sell_symbols

    def test_generate_signals_empty_universe(self):
        strategy = MultiFactorStrategy(factors=[PBValueFactor()], weights=[1.0], top_n=5)
        signals = strategy.generate_cross_sectional_signals(
            universe=[], current_positions=[], current_date=datetime(2024, 6, 15),
        )
        assert signals == []

    def test_name_property(self):
        strategy = MultiFactorStrategy(factors=[], weights=[], top_n=5)
        assert strategy.name == "MultiFactorStrategy"
