"""QMT 行情网关集成测试。

测试 get_market_data_ex 接口（新版API）的正确性。
"""

from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from src.domain.market.value_objects.timeframe import Timeframe
from src.infrastructure.gateway.qmt_market import QmtMarketGateway


class TestQmtMarketGateway:
    @pytest.fixture
    def mock_xtdata(self):
        with patch("src.infrastructure.gateway.qmt_market.xtdata") as mock:
            yield mock

    def test_get_recent_bars_should_return_mapped_bars(self, mock_xtdata):
        """测试 get_recent_bars 使用 get_market_data_ex 返回正确格式的数据。"""
        # Arrange
        gateway = QmtMarketGateway()
        symbol = "600000.SH"
        timeframe = Timeframe.DAY_1
        limit = 10

        # 创建模拟数据 - get_market_data_ex 返回 {stock: DataFrame(index=time, columns=fields)}
        timestamps = [1672531200000, 1672617600000]  # 2023-01-01, 2023-01-02
        df = pd.DataFrame({
            "open": [10.0, 10.5],
            "high": [11.0, 11.5],
            "low": [9.0, 9.5],
            "close": [10.5, 11.0],
            "volume": [1000, 2000],
        }, index=timestamps)

        # 模拟 get_market_data_ex 返回前复权数据
        mock_xtdata.get_market_data_ex.return_value = {symbol: df}

        # Act
        bars = gateway.get_recent_bars(symbol, timeframe, limit)

        # Assert
        assert len(bars) == 2
        assert bars[0].symbol == symbol
        assert bars[0].open == 10.0
        assert bars[0].close == 10.5
        assert bars[0].timestamp == datetime.fromtimestamp(timestamps[0] / 1000)

        assert bars[1].symbol == symbol
        assert bars[1].open == 10.5
        assert bars[1].close == 11.0

    def test_get_recent_bars_empty_data_should_return_empty_list(self, mock_xtdata):
        """测试当没有数据时返回空列表。"""
        # Arrange
        gateway = QmtMarketGateway()
        symbol = "600000.SH"

        # Mock empty return
        mock_xtdata.get_market_data_ex.return_value = {}

        # Act
        bars = gateway.get_recent_bars(symbol, Timeframe.DAY_1)

        # Assert
        assert bars == []

    def test_get_recent_bars_symbol_not_in_data_should_return_empty_list(self, mock_xtdata):
        """测试当标的不在数据中时返回空列表。"""
        # Arrange
        gateway = QmtMarketGateway()
        symbol = "600000.SH"

        # 创建模拟数据，但使用不同的标的
        df = pd.DataFrame({
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],
            "volume": [1000],
        }, index=[1672531200000])

        mock_xtdata.get_market_data_ex.return_value = {"OTHER.SH": df}

        # Act
        bars = gateway.get_recent_bars(symbol, Timeframe.DAY_1)

        # Assert
        assert bars == []

    def test_get_recent_bars_with_string_timestamp_should_parse_correctly(self, mock_xtdata):
        """测试当时间戳是字符串格式时能正确解析。"""
        # Arrange
        gateway = QmtMarketGateway()
        symbol = "600000.SH"
        timeframe = Timeframe.DAY_1

        # 创建模拟数据，使用字符串时间戳
        df = pd.DataFrame({
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],
            "volume": [1000],
        }, index=["20230101"])

        mock_xtdata.get_market_data_ex.return_value = {symbol: df}

        # Act
        bars = gateway.get_recent_bars(symbol, timeframe)

        # Assert
        assert len(bars) == 1
        assert bars[0].timestamp == datetime(2023, 1, 1)

    def test_get_recent_bars_should_fetch_unadjusted_close(self, mock_xtdata):
        """测试会获取不复权收盘价用于真实账本结算。"""
        # Arrange
        gateway = QmtMarketGateway()
        symbol = "600000.SH"
        timeframe = Timeframe.DAY_1

        timestamps = [1672531200000]
        df_adjusted = pd.DataFrame({
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],  # 前复权收盘价
            "volume": [1000],
        }, index=timestamps)

        df_unadjusted = pd.DataFrame({
            "close": [10.8],  # 不复权收盘价
        }, index=timestamps)

        # 第一次调用返回前复权数据，第二次调用返回不复权数据
        mock_xtdata.get_market_data_ex.side_effect = [
            {symbol: df_adjusted},
            {symbol: df_unadjusted},
        ]

        # Act
        bars = gateway.get_recent_bars(symbol, timeframe)

        # Assert
        assert len(bars) == 1
        assert bars[0].close == 10.5  # 前复权收盘价
        assert bars[0].unadjusted_close == 10.8  # 不复权收盘价
