import pytest
from unittest.mock import MagicMock, patch, call
import pandas as pd
from datetime import datetime
from src.infrastructure.gateway.qmt_history_data import QmtHistoryDataFetcher
from src.domain.market.value_objects.timeframe import Timeframe

class TestQmtHistoryDataFetcher:

    @pytest.fixture
    def mock_xtdata(self):
        with patch("src.infrastructure.gateway.qmt_history_data.xtdata") as mock:
            yield mock

    @pytest.fixture
    def fetcher(self):
        return QmtHistoryDataFetcher()

    @pytest.fixture
    def mock_to_csv(self):
        with patch("pandas.DataFrame.to_csv") as mock:
            yield mock

    @pytest.fixture
    def mock_path(self):
        with patch("src.infrastructure.gateway.qmt_history_data.Path") as mock:
            # Mock exists() to return False so it triggers download
            mock.return_value.exists.return_value = False
            # Mock division operator / to return another mock
            mock.return_value.__truediv__.return_value = mock.return_value
            yield mock

    def test_fetch_history_bars_should_download_financial_and_history_data(self, fetcher, mock_xtdata, mock_to_csv, mock_path):
        # Arrange
        symbol = "000001.SZ"
        timeframe = Timeframe.DAY_1
        start_date = "2023-01-01"
        end_date = "2023-01-02"
        
        # Mock download_history_data2 to trigger callback immediately
        def side_effect_download(stock_list, period, start_time, end_time, callback):
            callback({"stock_code": symbol, "finished": True})
            
        mock_xtdata.download_history_data2.side_effect = side_effect_download
        
        # Mock get_market_data_ex return value
        # DataFrame with datetime index
        dates = pd.to_datetime(["2023-01-01", "2023-01-02"])
        df = pd.DataFrame({
            "time": [1672531200000, 1672617600000],
            "open": [10.0, 10.5],
            "high": [11.0, 11.5],
            "low": [9.0, 9.5],
            "close": [10.5, 11.0],
            "volume": [1000, 2000]
        }, index=dates)
        
        mock_xtdata.get_market_data_ex.return_value = {symbol: df}

        # Act
        bars = fetcher.fetch_history_bars(symbol, timeframe, start_date, end_date)

        # Assert
        # 1. Verify financial data download (for forward adjustment)
        mock_xtdata.download_financial_data.assert_called_once_with(stock_list=[symbol])
        
        # 2. Verify history data download
        mock_xtdata.download_history_data2.assert_called_once()
        args, kwargs = mock_xtdata.download_history_data2.call_args
        assert kwargs['stock_list'] == [symbol]
        assert kwargs['period'] == '1d'
        assert kwargs['start_time'] == '20230101'
        assert kwargs['end_time'] == '20230102'
        assert 'callback' in kwargs
        
        # 3. Verify get_market_data_ex call with dividend_type='front'
        mock_xtdata.get_market_data_ex.assert_called_once()
        _, kwargs_get = mock_xtdata.get_market_data_ex.call_args
        assert kwargs_get['stock_list'] == [symbol]
        assert kwargs_get['dividend_type'] == 'front'
        
        # 4. Verify result bars
        assert len(bars) == 2
        assert bars[0].symbol == symbol
        assert bars[0].close == 10.5
        assert bars[0].volume == 1000

    def test_fetch_history_bars_should_wait_for_callback(self, fetcher, mock_xtdata):
        # This test verifies that the threading.Event logic is in place.
        # Since we cannot easily mock threading.Event inside the function without more patching,
        # we rely on the fact that if download_history_data2 doesn't trigger callback, 
        # the function might hang or timeout (if we didn't mock it to trigger).
        # Here we just verify the call structure.
        
        symbol = "000001.SZ"
        timeframe = Timeframe.DAY_1
        
        # Mock to NOT trigger callback immediately (simulate async)
        # But we need to patch threading.Event to avoid actual waiting in test
        with patch("src.infrastructure.gateway.qmt_history_data.Event") as MockEvent:
            event_instance = MockEvent.return_value
            event_instance.wait.return_value = True # Simulate wait success
            
            # Mock get_market_data_ex to return empty to avoid processing
            mock_xtdata.get_market_data_ex.return_value = {}
            
            fetcher.fetch_history_bars(symbol, timeframe, "2023-01-01", "2023-01-02")
            
            # Verify Event was created and wait was called
            MockEvent.assert_called_once()
            event_instance.wait.assert_called_once_with(timeout=60)

