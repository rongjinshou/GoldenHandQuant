import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import datetime
from src.infrastructure.gateway.tushare_fundamental_fetcher import TushareFundamentalFetcher


class TestTushareFundamentalFetcher:
    @pytest.fixture
    def mock_ts(self):
        with patch("src.infrastructure.gateway.tushare_fundamental_fetcher.ts") as mock:
            yield mock

    @pytest.fixture
    def fetcher(self, mock_ts):
        return TushareFundamentalFetcher(token="dummy_token")

    def test_fetch_by_range_should_return_snapshots(self, fetcher, mock_ts):
        # Arrange
        start_date = "2024-01-01"
        end_date = "2024-01-02"

        # Mock stock_basic
        df_basic = pd.DataFrame({
            "ts_code": ["000001.SZ", "600000.SH"],
            "name": ["平安银行", "浦发银行"],
            "list_date": ["19910403", "19991110"],
        })
        fetcher.pro.stock_basic.return_value = df_basic

        # Mock daily_basic
        df_daily = pd.DataFrame({
            "ts_code": ["000001.SZ", "600000.SH"],
            "trade_date": ["20240102", "20240102"],
            "total_mv": [3000000.0, 2000000.0],
        })
        fetcher.pro.daily_basic.return_value = df_daily

        # Mock fina_indicator
        df_fina = pd.DataFrame({
            "ts_code": ["000001.SZ", "600000.SH"],
            "ann_date": ["20240102", "20240102"],
            "roe_ttm": [12.5, 10.0],
            "ocf_ttm": [5.0, 3.0],
        })
        fetcher.pro.fina_indicator.return_value = df_fina

        # Act
        snapshots = fetcher.fetch_by_range(start_date, end_date)

        # Assert
        assert len(snapshots) == 2
        assert snapshots[0].symbol == "000001.SZ"
        assert snapshots[0].name == "平安银行"
        assert snapshots[0].market_cap == 3000000.0 * 10000
        assert snapshots[0].roe_ttm == 12.5
        assert snapshots[0].ocf_ttm == 5.0

    def test_fetch_by_range_empty_daily_basic(self, fetcher, mock_ts):
        # Arrange
        fetcher.pro.stock_basic.return_value = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "name": ["平安银行"],
            "list_date": ["19910403"],
        })
        fetcher.pro.daily_basic.return_value = pd.DataFrame()
        fetcher.pro.fina_indicator.return_value = pd.DataFrame()

        # Act
        snapshots = fetcher.fetch_by_range("2024-01-01", "2024-01-02")

        # Assert
        assert len(snapshots) == 0

    def test_fetch_by_range_missing_fina_data(self, fetcher, mock_ts):
        # Arrange
        fetcher.pro.stock_basic.return_value = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "name": ["平安银行"],
            "list_date": ["19910403"],
        })
        fetcher.pro.daily_basic.return_value = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240102"],
            "total_mv": [3000000.0],
        })
        fetcher.pro.fina_indicator.return_value = None

        # Act
        snapshots = fetcher.fetch_by_range("2024-01-01", "2024-01-02")

        # Assert
        assert len(snapshots) == 1
        assert snapshots[0].roe_ttm is None
        assert snapshots[0].ocf_ttm is None

    def test_fetch_by_range_no_token_raises(self, mock_ts):
        # Arrange
        mock_ts.set_token = MagicMock()
        mock_ts.pro_api.return_value = MagicMock()
        fetcher = TushareFundamentalFetcher(token=None)
        fetcher.pro = None

        # Act & Assert
        with pytest.raises(ImportError):
            fetcher.fetch_by_range("2024-01-01", "2024-01-02")
