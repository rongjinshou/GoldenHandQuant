import pandas as pd
from datetime import datetime, timedelta
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe

class TestMockMarketGateway:
    def test_add_bars_should_classify_by_timeframe(self):
        # Arrange
        gateway = MockMarketGateway()
        now = datetime.now()
        
        bar_1m = Bar(symbol="S1", timeframe=Timeframe.MIN_1, timestamp=now, open=10, high=10, low=10, close=10, volume=100)
        bar_1d = Bar(symbol="S1", timeframe=Timeframe.DAY_1, timestamp=now, open=10, high=10, low=10, close=10, volume=100)
        
        # Act
        gateway.add_bars("S1", [bar_1m, bar_1d])
        
        # Assert
        assert len(gateway.data["S1"][Timeframe.MIN_1]) == 1
        assert len(gateway.data["S1"][Timeframe.DAY_1]) == 1
        assert gateway.data["S1"][Timeframe.MIN_1][0] == bar_1m
        assert gateway.data["S1"][Timeframe.DAY_1][0] == bar_1d

    def test_get_recent_bars_should_filter_by_timeframe_and_time(self):
        # Arrange
        gateway = MockMarketGateway()
        now = datetime(2023, 1, 1, 10, 0)
        
        bars = [
            Bar(symbol="S1", timeframe=Timeframe.MIN_1, timestamp=now - timedelta(minutes=2), open=10, high=10, low=10, close=10, volume=100),
            Bar(symbol="S1", timeframe=Timeframe.MIN_1, timestamp=now - timedelta(minutes=1), open=11, high=11, low=11, close=11, volume=100),
            Bar(symbol="S1", timeframe=Timeframe.MIN_1, timestamp=now, open=12, high=12, low=12, close=12, volume=100),
            Bar(symbol="S1", timeframe=Timeframe.MIN_1, timestamp=now + timedelta(minutes=1), open=13, high=13, low=13, close=13, volume=100), # Future
        ]
        gateway.add_bars("S1", bars)
        
        gateway.set_current_time(now)
        
        # Act
        recent_bars = gateway.get_recent_bars("S1", Timeframe.MIN_1, limit=2)
        
        # Assert
        assert len(recent_bars) == 2
        assert recent_bars[0].timestamp == now - timedelta(minutes=1)
        assert recent_bars[1].timestamp == now

    def test_get_all_timestamps_should_return_sorted_unique_timestamps(self):
        # Arrange
        gateway = MockMarketGateway()
        now = datetime(2023, 1, 1, 10, 0)
        
        # S1 has bars at T1, T2
        # S2 has bars at T2, T3
        t1 = now
        t2 = now + timedelta(minutes=1)
        t3 = now + timedelta(minutes=2)
        
        gateway.add_bars("S1", [
            Bar(symbol="S1", timeframe=Timeframe.MIN_1, timestamp=t1, open=10, high=10, low=10, close=10, volume=100),
            Bar(symbol="S1", timeframe=Timeframe.MIN_1, timestamp=t2, open=10, high=10, low=10, close=10, volume=100),
        ])
        gateway.add_bars("S2", [
            Bar(symbol="S2", timeframe=Timeframe.MIN_1, timestamp=t2, open=10, high=10, low=10, close=10, volume=100),
            Bar(symbol="S2", timeframe=Timeframe.MIN_1, timestamp=t3, open=10, high=10, low=10, close=10, volume=100),
        ])
        
        # Act
        timestamps = gateway.get_all_timestamps(Timeframe.MIN_1)
        
        # Assert
        assert len(timestamps) == 3
        assert timestamps == [t1, t2, t3]

    def test_load_data_should_respect_timeframe(self):
        # Arrange
        gateway = MockMarketGateway()
        data = {
            "datetime": [datetime(2023, 1, 1), datetime(2023, 1, 2)],
            "symbol": ["S1", "S1"],
            "open": [10, 11],
            "high": [10, 11],
            "low": [10, 11],
            "close": [10, 11],
            "volume": [100, 100]
        }
        df = pd.DataFrame(data)
        
        # Act
        gateway.load_data(df, timeframe=Timeframe.DAY_1)
        
        # Assert
        assert len(gateway.data["S1"][Timeframe.DAY_1]) == 2
        assert gateway.data["S1"][Timeframe.DAY_1][0].timeframe == Timeframe.DAY_1
