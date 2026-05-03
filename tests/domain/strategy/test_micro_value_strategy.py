from datetime import datetime
from src.domain.strategy.services.strategies.micro_value_strategy import MicroValueStrategy
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.market.value_objects.stock_snapshot import StockSnapshot

def _snap(symbol, mcap, close=10.2, **kwargs):
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 6, 11),  # Tuesday
        open=10.0, high=10.5, low=9.8, close=close, volume=1e6,
        name="Normal Stock", list_date=datetime(2000, 1, 1),
        market_cap=mcap, roe_ttm=0.20, ocf_ttm=1e8, **kwargs
    )

class TestMicroValueStrategy:
    def test_calendar_circuit_breaker_january_returns_empty(self):
        strategy = MicroValueStrategy(top_n=5)
        universe = [_snap("A", 1e9), _snap("B", 2e9), _snap("C", 3e9), _snap("D", 4e9), _snap("E", 5e9)]
        jan_date = datetime(2024, 1, 9)  # Tuesday in January
        signals = strategy.generate_cross_sectional_signals(universe, [], jan_date)
        assert signals == []

    def test_calendar_circuit_breaker_april_returns_empty(self):
        strategy = MicroValueStrategy(top_n=5)
        universe = [_snap("A", 1e9) for _ in range(5)]
        apr_date = datetime(2024, 4, 9)  # Tuesday in April
        signals = strategy.generate_cross_sectional_signals(universe, [], apr_date)
        assert signals == []

    def test_non_tuesday_returns_empty(self):
        strategy = MicroValueStrategy(top_n=5)
        universe = [_snap("A", 1e9) for _ in range(10)]
        monday = datetime(2024, 6, 10)  # Monday
        signals = strategy.generate_cross_sectional_signals(universe, [], monday)
        assert signals == []

    def test_tuesday_produces_top_n_buy_signals(self):
        strategy = MicroValueStrategy(top_n=3)
        universe = [
            _snap("B", 2e9), _snap("A", 1e9), _snap("D", 4e9),
            _snap("C", 3e9), _snap("E", 5e9),
        ]
        tuesday = datetime(2024, 6, 11)  # Tuesday
        signals = strategy.generate_cross_sectional_signals(universe, [], tuesday)
        assert len(signals) == 3
        # Should be A, B, C (mcap: 1e9, 2e9, 3e9)
        assert signals[0].symbol == "A"
        assert signals[1].symbol == "B"
        assert signals[2].symbol == "C"
        for s in signals:
            assert s.direction == SignalDirection.BUY
            assert s.strategy_name == "MicroValueStrategy"

    def test_filters_penny_stocks_before_ranking(self):
        strategy = MicroValueStrategy(top_n=3)
        universe = [
            _snap("Penny", 1e8, close=1.0),  # filtered out
            _snap("A", 1e9, close=10.0),
            _snap("B", 2e9, close=10.0),
            _snap("C", 3e9, close=10.0),
            _snap("D", 4e9, close=10.0),
        ]
        tuesday = datetime(2024, 6, 11)
        signals = strategy.generate_cross_sectional_signals(universe, [], tuesday)
        assert len(signals) == 3
        assert "Penny" not in {s.symbol for s in signals}

    def test_name_property(self):
        assert MicroValueStrategy().name == "MicroValueStrategy"
