from datetime import datetime
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe

class TestBar:
    def test_init_should_store_values_correctly(self):
        # Arrange
        now = datetime.now()
        
        # Act
        bar = Bar(
            symbol="600000.SH",
            timeframe=Timeframe.DAY_1,
            timestamp=now,
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.5,
            volume=1000.0
        )
        
        # Assert
        assert bar.symbol == "600000.SH"
        assert bar.timeframe == Timeframe.DAY_1
        assert bar.timestamp == now
        assert bar.open == 10.0
        assert bar.high == 11.0
        assert bar.low == 9.0
        assert bar.close == 10.5
        assert bar.volume == 1000.0

    def test_bar_unadjusted_close_defaults_to_zero(self):
        """向后兼容：未提供 unadjusted_close 时默认为 0.0。"""
        bar = Bar(
            symbol="000001.SZ", timeframe=Timeframe.DAY_1,
            timestamp=datetime(2024, 1, 3),
            open=10.0, high=11.0, low=9.5, close=10.5, volume=10000,
        )
        assert bar.unadjusted_close == 0.0

    def test_bar_with_unadjusted_close(self):
        """提供 unadjusted_close 时正确存储，且不影响复权价。"""
        bar = Bar(
            symbol="000001.SZ", timeframe=Timeframe.DAY_1,
            timestamp=datetime(2024, 1, 3),
            open=5.0, high=5.5, low=4.8, close=5.2, volume=10000,
            unadjusted_close=20.5,
        )
        assert bar.unadjusted_close == 20.5
        assert bar.close == 5.2  # 复权价不变
