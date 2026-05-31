"""QMT 历史数据获取器集成测试。

测试 fetch_history_bars 方法的正确性。
"""

import pytest
from unittest.mock import MagicMock, patch
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

    def test_fetch_history_bars_should_download_and_return_bars(self, fetcher, mock_xtdata, mock_to_csv, mock_path):
        """测试 fetch_history_bars 正确下载数据并返回 Bar 列表。"""
        # Arrange
        symbol = "000001.SZ"
        timeframe = Timeframe.DAY_1
        start_date = "2023-01-01"
        end_date = "2023-01-02"

        # Mock get_market_data_ex 返回前复权数据
        timestamps = [1672531200000, 1672617600000]
        df = pd.DataFrame({
            "open": [10.0, 10.5],
            "high": [11.0, 11.5],
            "low": [9.0, 9.5],
            "close": [10.5, 11.0],
            "volume": [1000, 2000],
        }, index=timestamps)
        df.index.name = 'datetime'

        # 第一次调用返回前复权数据，第二次调用返回不复权数据
        df_unadjusted = pd.DataFrame({
            "close": [10.8, 11.2],
        }, index=timestamps)

        mock_xtdata.get_market_data_ex.side_effect = [
            {symbol: df},  # 前复权数据
            {symbol: df_unadjusted},  # 不复权数据
        ]

        # Act
        bars = fetcher.fetch_history_bars(symbol, timeframe, start_date, end_date)

        # Assert
        # 1. Verify history data download was called
        mock_xtdata.download_history_data.assert_called_once()

        # 2. Verify get_market_data_ex call with dividend_type='front'
        assert mock_xtdata.get_market_data_ex.call_count == 2
        first_call_kwargs = mock_xtdata.get_market_data_ex.call_args_list[0][1]
        assert first_call_kwargs['stock_list'] == [symbol]
        assert first_call_kwargs['dividend_type'] == 'front'

        # 3. Verify result bars
        assert len(bars) == 2
        assert bars[0].symbol == symbol
        assert bars[0].close == 10.5
        assert bars[0].volume == 1000

    def test_fetch_history_bars_with_cached_data_should_use_cache(self, fetcher, mock_xtdata):
        """测试当本地缓存存在时使用缓存数据。"""
        # Arrange
        symbol = "000001.SZ"
        timeframe = Timeframe.DAY_1
        start_date = "2023-01-01"
        end_date = "2023-01-02"

        # 创建缓存数据
        cached_df = pd.DataFrame({
            "datetime": pd.to_datetime(["2023-01-01", "2023-01-02"]),
            "open": [10.0, 10.5],
            "high": [11.0, 11.5],
            "low": [9.0, 9.5],
            "close": [10.5, 11.0],
            "volume": [1000, 2000],
        })

        # Mock Path.exists() 返回 True，表示缓存存在
        with patch("src.infrastructure.gateway.qmt_history_data.Path") as mock_path:
            mock_path.return_value.exists.return_value = True

            # Mock pd.read_csv 返回缓存数据
            with patch("pandas.read_csv", return_value=cached_df):
                # Mock get_market_data_ex 返回不复权数据
                df_unadjusted = pd.DataFrame({
                    "close": [10.8, 11.2],
                }, index=[1672531200000, 1672617600000])

                mock_xtdata.get_market_data_ex.return_value = {symbol: df_unadjusted}

                # Act
                bars = fetcher.fetch_history_bars(symbol, timeframe, start_date, end_date)

                # Assert
                # 不应该调用 download_history_data，因为使用了缓存
                mock_xtdata.download_history_data.assert_not_called()

                # 应该返回缓存的数据
                assert len(bars) == 2
                assert bars[0].close == 10.5

    def test_fetch_history_bars_empty_data_should_return_empty_list(self, fetcher, mock_xtdata, mock_path):
        """测试当没有数据时返回空列表。"""
        # Arrange
        symbol = "000001.SZ"
        timeframe = Timeframe.DAY_1
        start_date = "2023-01-01"
        end_date = "2023-01-02"

        # Mock get_market_data_ex 返回空数据
        mock_xtdata.get_market_data_ex.return_value = {}

        # Act
        bars = fetcher.fetch_history_bars(symbol, timeframe, start_date, end_date)

        # Assert
        assert bars == []

    def test_fetch_history_bars_should_convert_time_format(self, fetcher, mock_xtdata, mock_path):
        """测试时间格式从 YYYY-MM-DD 转换为 YYYYMMDD。"""
        # Arrange
        symbol = "000001.SZ"
        timeframe = Timeframe.DAY_1
        start_date = "2023-01-01"
        end_date = "2023-01-15"

        # Mock get_market_data_ex 返回空数据（简化测试）
        mock_xtdata.get_market_data_ex.return_value = {}

        # Act
        fetcher.fetch_history_bars(symbol, timeframe, start_date, end_date)

        # Assert
        # 验证 download_history_data 被调用时使用了正确的时间格式
        call_kwargs = mock_xtdata.download_history_data.call_args[1]
        assert call_kwargs['start_time'] == '20230101'
        assert call_kwargs['end_time'] == '20230115'
