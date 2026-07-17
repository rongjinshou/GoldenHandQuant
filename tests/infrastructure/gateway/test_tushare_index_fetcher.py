from unittest.mock import patch

import pandas as pd
import pytest

from src.infrastructure.gateway.tushare_index_fetcher import TushareIndexFetcher


class TestTushareIndexFetcher:
    @pytest.fixture
    def mock_ts(self):
        with patch("src.infrastructure.gateway.tushare_index_fetcher.ts") as mock:
            yield mock

    @pytest.fixture
    def fetcher(self, mock_ts):
        return TushareIndexFetcher(token="dummy_token")

    def test_fetch_index_daily_should_return_sorted_list(self, fetcher, mock_ts):
        # Arrange
        index_symbol = "000852.SH"
        df = pd.DataFrame({
            "trade_date": ["20240102", "20240101"],
            "open": [5000.0, 4950.0],
            "high": [5100.0, 5050.0],
            "low": [4900.0, 4900.0],
            "close": [5050.0, 5000.0],
            "vol": [1000000, 800000],
        })
        fetcher.pro.index_daily.return_value = df

        # Act
        results = fetcher.fetch_index_daily(index_symbol, "2024-01-01", "2024-01-02")

        # Assert
        assert len(results) == 2
        # Should be sorted ascending by trade_date
        assert results[0]["trade_date"] == "20240101"
        assert results[0]["close"] == 5000.0
        assert results[0]["volume"] == 800000
        assert results[1]["trade_date"] == "20240102"
        assert results[1]["close"] == 5050.0

    def test_fetch_index_daily_empty_response(self, fetcher, mock_ts):
        # Arrange
        fetcher.pro.index_daily.return_value = pd.DataFrame()

        # Act
        results = fetcher.fetch_index_daily("000852.SH", "2024-01-01", "2024-01-02")

        # Assert
        assert len(results) == 0

    def test_fetch_index_daily_none_response(self, fetcher, mock_ts):
        # Arrange
        fetcher.pro.index_daily.return_value = None

        # Act
        results = fetcher.fetch_index_daily("000852.SH", "2024-01-01", "2024-01-02")

        # Assert
        assert len(results) == 0

    def test_fetch_index_daily_no_token_raises(self, mock_ts):
        # Arrange
        fetcher = TushareIndexFetcher(token=None)
        fetcher.pro = None

        # Act & Assert
        with pytest.raises(ImportError):
            fetcher.fetch_index_daily("000852.SH", "2024-01-01", "2024-01-02")

    def test_fetch_index_daily_date_format_conversion(self, fetcher, mock_ts):
        # Arrange
        df = pd.DataFrame({
            "trade_date": ["20240102"],
            "open": [5000.0],
            "high": [5100.0],
            "low": [4900.0],
            "close": [5050.0],
            "vol": [1000000],
        })
        fetcher.pro.index_daily.return_value = df

        # Act - pass dates with dashes
        results = fetcher.fetch_index_daily("000852.SH", "2024-01-01", "2024-01-02")

        # Assert - verify API called with stripped dates
        fetcher.pro.index_daily.assert_called_once_with(
            ts_code="000852.SH", start_date="20240101", end_date="20240102"
        )
        assert len(results) == 1
