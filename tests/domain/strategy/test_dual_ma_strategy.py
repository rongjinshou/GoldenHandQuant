import pytest
from datetime import datetime, timedelta
from src.domain.strategy.services.strategies.dual_ma_strategy import DualMaStrategy
from src.domain.market.value_objects.bar import Bar
from src.domain.account.entities.position import Position
from src.domain.strategy.value_objects.signal_direction import SignalDirection

class TestDualMaStrategy:
    def _create_bars(self, prices: list[float]) -> list[Bar]:
        bars = []
        base_time = datetime.now() - timedelta(days=len(prices))
        for i, price in enumerate(prices):
            bar = Bar(
                symbol="600000.SH",
                timestamp=base_time + timedelta(days=i),
                open=price, high=price, low=price, close=price, volume=1000
            )
            bars.append(bar)
        return bars

    def test_generate_signals_golden_cross_should_buy(self):
        # Arrange
        strategy = DualMaStrategy()
        
        # Construct prices to trigger Golden Cross
        # MA5 crosses above MA10
        # Let's say MA10 is flat at 10.0
        # MA5 goes from 9.0 to 11.0
        
        # We need 11 bars minimum.
        # Prev state (T-1): MA5 <= MA10
        # Curr state (T): MA5 > MA10
        
        # Simplified scenario:
        # Bars 0-9 (10 bars): all 10.0. 
        #   MA10 prev (0-9) = 10.0
        #   MA5 prev (5-9) = 10.0
        # Bar 10: 20.0
        #   MA10 curr (1-10) = (9*10 + 20)/10 = 11.0
        #   MA5 curr (6-10) = (4*10 + 20)/5 = 12.0
        
        # Wait, if Prev: MA5=10, MA10=10 -> MA5 <= MA10 is True.
        # Curr: MA5=12, MA10=11 -> MA5 > MA10 is True.
        # Golden Cross!
        
        prices = [10.0] * 10 + [20.0]
        bars = self._create_bars(prices)
        market_data = {"600000.SH": bars}
        positions = []

        # Act
        signals = strategy.generate_signals(market_data, positions)

        # Assert
        assert len(signals) == 1
        signal = signals[0]
        assert signal.symbol == "600000.SH"
        assert signal.direction == SignalDirection.BUY
        assert signal.target_volume == 100
        assert "Golden Cross" in signal.reason

    def test_generate_signals_death_cross_should_sell_if_position_exists(self):
        # Arrange
        strategy = DualMaStrategy()
        
        # Construct prices to trigger Death Cross
        # Prev: MA5 >= MA10
        # Curr: MA5 < MA10
        
        # Bars 0-9: all 20.0
        #   MA10 prev = 20.0
        #   MA5 prev = 20.0
        # Bar 10: 10.0
        #   MA10 curr (1-10) = (9*20 + 10)/10 = 19.0
        #   MA5 curr (6-10) = (4*20 + 10)/5 = 18.0
        # 18.0 < 19.0 -> Death Cross
        
        prices = [20.0] * 10 + [10.0]
        bars = self._create_bars(prices)
        market_data = {"600000.SH": bars}
        
        # Position exists
        pos = Position(
            account_id="acc", 
            ticker="600000.SH", 
            total_volume=500, 
            available_volume=500
        )
        positions = [pos]

        # Act
        signals = strategy.generate_signals(market_data, positions)

        # Assert
        assert len(signals) == 1
        signal = signals[0]
        assert signal.symbol == "600000.SH"
        assert signal.direction == SignalDirection.SELL
        assert signal.target_volume == 500
        assert "Death Cross" in signal.reason

    def test_generate_signals_death_cross_no_position_should_not_sell(self):
        # Arrange
        strategy = DualMaStrategy()
        
        prices = [20.0] * 10 + [10.0] # Death Cross
        bars = self._create_bars(prices)
        market_data = {"600000.SH": bars}
        positions = [] # No position

        # Act
        signals = strategy.generate_signals(market_data, positions)

        # Assert
        assert len(signals) == 0

    def test_generate_signals_insufficient_data_should_return_empty(self):
        # Arrange
        strategy = DualMaStrategy()
        prices = [10.0] * 5 # Only 5 bars
        bars = self._create_bars(prices)
        market_data = {"600000.SH": bars}
        positions = []

        # Act
        signals = strategy.generate_signals(market_data, positions)

        # Assert
        assert len(signals) == 0
