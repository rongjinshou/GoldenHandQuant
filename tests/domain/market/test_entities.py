from datetime import datetime
from src.domain.market.entities import Bar

class TestBar:
    def test_init_should_store_values_correctly(self):
        # Arrange
        now = datetime.now()
        
        # Act
        bar = Bar(
            symbol="600000.SH",
            timestamp=now,
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.5,
            volume=1000.0
        )
        
        # Assert
        assert bar.symbol == "600000.SH"
        assert bar.timestamp == now
        assert bar.open == 10.0
        assert bar.high == 11.0
        assert bar.low == 9.0
        assert bar.close == 10.5
        assert bar.volume == 1000.0
