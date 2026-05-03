import pytest
from datetime import datetime
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.account.entities.position import Position
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection

class _ConcreteCS(CrossSectionalStrategy):
    @property
    def name(self) -> str:
        return "TestCS"

    def generate_cross_sectional_signals(self, universe, current_positions, current_date):
        return [
            Signal(symbol=s.symbol, direction=SignalDirection.BUY,
                   confidence_score=1.0, strategy_name=self.name)
            for s in universe
        ]

class TestCrossSectionalStrategy:
    def test_generate_signals_raises_not_implemented(self):
        strategy = _ConcreteCS()
        with pytest.raises(NotImplementedError, match="generate_cross_sectional_signals"):
            strategy.generate_signals({}, [])

    def test_isinstance_of_base_strategy(self):
        from src.domain.strategy.services.base_strategy import BaseStrategy
        strategy = _ConcreteCS()
        assert isinstance(strategy, BaseStrategy)

    def test_concrete_implementation_works(self):
        strategy = _ConcreteCS()
        snap = StockSnapshot(
            symbol="000001.SZ", date=datetime(2024, 6, 15),
            open=10.0, high=10.5, low=9.8, close=10.2, volume=1e6,
            name="Test", list_date=datetime(2000, 1, 1), market_cap=1e10,
        )
        signals = strategy.generate_cross_sectional_signals(
            [snap], [], datetime(2024, 6, 15)
        )
        assert len(signals) == 1
        assert signals[0].symbol == "000001.SZ"
