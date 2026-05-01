import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import datetime
from src.infrastructure.gateway.tushare_history_data import TushareHistoryDataFetcher
from src.domain.market.value_objects.timeframe import Timeframe


class TestTushareHistoryDataFetcher:
    @pytest.fixture
    def mock_ts(self):
        with patch("src.infrastructure.gateway.tushare_history_data.ts") as mock:
            yield mock

    @pytest.fixture
    def fetcher(self, mock_ts):
        return TushareHistoryDataFetcher(token="dummy_token")

    @pytest.fixture
    def mock_to_csv(self):
        with patch("pandas.DataFrame.to_csv") as mock:
            yield mock

    @pytest.fixture
    def mock_path(self):
        with patch("src.infrastructure.gateway.tushare_history_data.Path") as mock:
            # Mock exists() to return False so it triggers download
            mock.return_value.exists.return_value = False
            # Mock division operator / to return another mock
            mock.return_value.__truediv__.return_value = mock.return_value
            yield mock

    def test_fetch_history_bars_should_download_data_from_tushare(self, fetcher, mock_ts, mock_to_csv, mock_path):
        # Arrange
        symbol = "000001.SZ"
        timeframe = Timeframe.DAY_1
        start_date = "2023-01-01"
        end_date = "2023-01-02"

        # Mock pro_bar return value
        df = pd.DataFrame({
            "ts_code": [symbol, symbol],
            "trade_date": ["20230102", "20230101"],
            "open": [10.5, 10.0],
            "high": [11.5, 11.0],
            "low": [9.5, 9.0],
            "close": [11.0, 10.5],
            "vol": [2000, 1000]
        })
        mock_ts.pro_bar.return_value = df

        # Act
        bars = fetcher.fetch_history_bars(symbol, timeframe, start_date, end_date)

        # Assert
        # 1. Verify Tushare download
        mock_ts.pro_bar.assert_called_once_with(
            ts_code=symbol,
            start_date="20230101",
            end_date="20230102",
            freq="D",
            adj="qfq"
        )

        # 2. Verify result bars
        assert len(bars) == 2
        # Tushare returns desc, our code sorts to asc
        assert bars[0].symbol == symbol
        assert bars[0].close == 10.5
        assert bars[0].volume == 1000
        assert bars[0].timestamp == datetime(2023, 1, 1)

        assert bars[1].symbol == symbol
        assert bars[1].close == 11.0
        assert bars[1].volume == 2000
        assert bars[1].timestamp == datetime(2023, 1, 2)

    def test_fetch_history_bars_empty_response(self, fetcher, mock_ts, mock_path):
        # Arrange
        symbol = "000001.SZ"
        timeframe = Timeframe.DAY_1
        
        # Mock empty DataFrame
        mock_ts.pro_bar.return_value = pd.DataFrame()

        # Act
        bars = fetcher.fetch_history_bars(symbol, timeframe, "2023-01-01", "2023-01-02")

        # Assert
        assert len(bars) == 0
