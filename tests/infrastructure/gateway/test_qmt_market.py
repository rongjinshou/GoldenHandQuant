import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import pandas as pd
from src.infrastructure.gateway.qmt_market import QmtMarketGateway
from src.domain.market.value_objects.timeframe import Timeframe

class TestQmtMarketGateway:
    @pytest.fixture
    def mock_xtdata(self):
        with patch("src.infrastructure.gateway.qmt_market.xtdata") as mock:
            yield mock

    def test_get_recent_bars_should_return_mapped_bars(self, mock_xtdata):
        # Arrange
        gateway = QmtMarketGateway()
        symbol = "600000.SH"
        timeframe = Timeframe.DAY_1
        limit = 10
        
        # Create mock data
        times = [1672531200000, 1672617600000] # 2023-01-01, 2023-01-02
        data = {
            "time": pd.DataFrame({"600000.SH": times}, index=times),
            "open": pd.DataFrame({"600000.SH": [10.0, 10.5]}, index=times),
            "high": pd.DataFrame({"600000.SH": [11.0, 11.5]}, index=times),
            "low": pd.DataFrame({"600000.SH": [9.0, 9.5]}, index=times),
            "close": pd.DataFrame({"600000.SH": [10.5, 11.0]}, index=times),
            "volume": pd.DataFrame({"600000.SH": [1000, 2000]}, index=times),
        }
        
        # Adjust the mock return structure to match qmt_market.py logic
        # data["time"] columns are times, index is stocks?
        # Re-reading qmt_market.py:
        # times = data[first_field].columns.tolist()
        # timestamps = data["time"].loc[symbol] -> so index is symbol, columns are times
        
        columns = times
        index = [symbol]
        
        mock_return = {
            "time": pd.DataFrame([times], index=index, columns=columns),
            "open": pd.DataFrame([[10.0, 10.5]], index=index, columns=columns),
            "high": pd.DataFrame([[11.0, 11.5]], index=index, columns=columns),
            "low": pd.DataFrame([[9.0, 9.5]], index=index, columns=columns),
            "close": pd.DataFrame([[10.5, 11.0]], index=index, columns=columns),
            "volume": pd.DataFrame([[1000, 2000]], index=index, columns=columns),
        }
        
        mock_xtdata.get_market_data.return_value = mock_return

        # Act
        bars = gateway.get_recent_bars(symbol, timeframe, limit)

        # Assert
        assert len(bars) == 2
        assert bars[0].symbol == symbol
        assert bars[0].open == 10.0
        assert bars[0].close == 10.5
        assert bars[0].timestamp == datetime.fromtimestamp(times[0] / 1000)
        
        assert bars[1].symbol == symbol
        assert bars[1].open == 10.5
        assert bars[1].close == 11.0

    def test_get_recent_bars_empty_data_should_return_empty_list(self, mock_xtdata):
        # Arrange
        gateway = QmtMarketGateway()
        symbol = "600000.SH"
        
        # Mock empty return
        mock_xtdata.get_market_data.return_value = {}

        # Act
        bars = gateway.get_recent_bars(symbol, Timeframe.DAY_1)

        # Assert
        assert bars == []

    def test_get_recent_bars_symbol_not_in_data_should_return_empty_list(self, mock_xtdata):
        # Arrange
        gateway = QmtMarketGateway()
        symbol = "600000.SH"
        
        times = [1672531200000]
        columns = times
        index = ["OTHER.SH"] # Different symbol
        
        mock_return = {
            "time": pd.DataFrame([times], index=index, columns=columns),
            "open": pd.DataFrame([[10.0]], index=index, columns=columns),
            # ... other fields
        }
        mock_xtdata.get_market_data.return_value = mock_return

        # Act
        bars = gateway.get_recent_bars(symbol, Timeframe.DAY_1)

        # Assert
        assert bars == []
