"""QMT 历史数据获取器集成测试。

测试 fetch_history_bars 方法的正确性。
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from src.domain.market.value_objects.timeframe import Timeframe
from src.infrastructure.gateway.qmt_history_data import QmtHistoryDataFetcher


def _ms(d: str) -> int:
    """日期字符串 -> QMT 毫秒时间戳。"""
    return int(pd.Timestamp(d).value // 10**6)


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

    def test_partial_cache_not_covering_end_should_refetch_full_range(self, fetcher, mock_xtdata):
        """缓存只到 1 月、却请求到 12 月时，应重拉完整区间，而非返回残缺缓存。

        复现根因 bug: mask.any() 命中即用缓存 -> 请求多年只回放缓存里那几个月。
        """
        symbol = "000001.SZ"
        timeframe = Timeframe.DAY_1
        start_date = "2024-01-01"
        end_date = "2024-12-31"

        # 缓存只覆盖 1 月头两天，远不到请求的 12-31
        cached_df = pd.DataFrame({
            "datetime": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "open": [10.0, 10.5], "high": [11.0, 11.5],
            "low": [9.0, 9.5], "close": [10.5, 11.0], "volume": [1000, 2000],
        })

        def _ms(d):
            return int(pd.Timestamp(d).value // 10**6)

        full_ts = [_ms("2024-01-02"), _ms("2024-06-03"), _ms("2024-12-31")]
        df_front = pd.DataFrame({
            "open": [10.0, 12.0, 14.0], "high": [11.0, 13.0, 15.0],
            "low": [9.0, 11.0, 13.0], "close": [10.5, 12.5, 14.5],
            "volume": [1000, 2000, 3000],
        }, index=full_ts)
        df_front.index.name = "datetime"
        df_unadj = pd.DataFrame({"close": [10.8, 12.8, 14.8]}, index=full_ts)

        with patch("src.infrastructure.gateway.qmt_history_data.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__truediv__.return_value = mock_path.return_value
            with patch("pandas.read_csv", return_value=cached_df):
                with patch("pandas.DataFrame.to_csv"):
                    mock_xtdata.get_market_data_ex.side_effect = [
                        {symbol: df_front},
                        {symbol: df_unadj},
                    ]
                    bars = fetcher.fetch_history_bars(
                        symbol, timeframe, start_date, end_date
                    )

        # 应检测到缓存未覆盖到 end -> 重新下载完整区间
        mock_xtdata.download_history_data.assert_called_once()
        # 返回的数据应延伸到 12 月，而非停在 1 月
        assert bars, "应返回 bar"
        last = max(b.timestamp for b in bars)
        assert (last.year, last.month) == (2024, 12)

    def test_cache_not_covering_start_should_refetch_full_range(self, fetcher, mock_xtdata):
        """缓存虽新鲜到 end、但起点晚于请求 start 时，应重拉完整区间。

        复现 start 侧缺口: 旧缓存只从 2024 起，请求 2020-06-15 起 (warmup)
        -> 旧逻辑静默截掉 2020-2023，因子测试前几年的数据悄悄消失。
        """
        symbol = "000001.SZ"
        timeframe = Timeframe.DAY_1
        start_date = "2020-06-15"
        end_date = "2025-12-31"

        # 缓存新鲜 (max 2026-02-13 >= end) 但起点只到 2024-01-02
        cached_df = pd.DataFrame({
            "datetime": pd.to_datetime(["2024-01-02", "2025-06-02", "2026-02-13"]),
            "open": [10.0, 10.5, 11.0], "high": [11.0, 11.5, 12.0],
            "low": [9.0, 9.5, 10.0], "close": [10.5, 11.0, 11.5],
            "volume": [1000, 2000, 3000],
        })

        full_ts = [_ms("2020-06-15"), _ms("2023-01-03"), _ms("2025-12-31")]
        df_front = pd.DataFrame({
            "open": [8.0, 10.0, 14.0], "high": [9.0, 11.0, 15.0],
            "low": [7.0, 9.0, 13.0], "close": [8.5, 10.5, 14.5],
            "volume": [1000, 2000, 3000],
        }, index=full_ts)
        df_front.index.name = "datetime"
        df_unadj = pd.DataFrame({"close": [8.8, 10.8, 14.8]}, index=full_ts)

        with patch("src.infrastructure.gateway.qmt_history_data.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__truediv__.return_value = mock_path.return_value
            with patch("pandas.read_csv", return_value=cached_df):
                with patch("pandas.DataFrame.to_csv"):
                    mock_xtdata.get_market_data_ex.side_effect = [
                        {symbol: df_front},
                        {symbol: df_unadj},
                    ]
                    bars = fetcher.fetch_history_bars(
                        symbol, timeframe, start_date, end_date
                    )

        # 应检测到缓存未覆盖 start -> 重新下载完整区间
        mock_xtdata.download_history_data.assert_called_once()
        # 返回的数据应回溯到 2020，而非从 2024 开始
        assert bars, "应返回 bar"
        first = min(b.timestamp for b in bars)
        assert first.year == 2020

    def test_meta_prevents_refetch_for_late_listed_symbol(self, fetcher, mock_xtdata):
        """晚上市股票: 缓存起点=上市日(晚于请求 start), 但 meta 记录
        已按该 start 完整拉取过 -> 用缓存, 不应每次重拉(防风暴)。
        """
        symbol = "000001.SZ"
        timeframe = Timeframe.DAY_1
        start_date = "2020-06-15"
        end_date = "2025-12-31"

        # 2022 年才上市: 缓存数据天然无法回溯到 2020
        cached_df = pd.DataFrame({
            "datetime": pd.to_datetime(["2022-05-10", "2024-01-02", "2025-12-31"]),
            "open": [10.0, 10.5, 11.0], "high": [11.0, 11.5, 12.0],
            "low": [9.0, 9.5, 10.0], "close": [10.5, 11.0, 11.5],
            "volume": [1000, 2000, 3000],
        })

        with patch("src.infrastructure.gateway.qmt_history_data.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__truediv__.return_value = mock_path.return_value
            # meta: 该 symbol 已按 2020-06-15 起完整下载过
            mock_path.return_value.read_text.return_value = json.dumps(
                {"000001.SZ_1d": "2020-06-15"}
            )
            with patch("pandas.read_csv", return_value=cached_df):
                mock_xtdata.get_market_data_ex.return_value = {
                    symbol: pd.DataFrame({"close": [10.8]}, index=[_ms("2022-05-10")])
                }
                bars = fetcher.fetch_history_bars(
                    symbol, timeframe, start_date, end_date
                )

        # meta 已确认 start 不可回溯更多 -> 直接用缓存, 不重新下载
        mock_xtdata.download_history_data.assert_not_called()
        assert len(bars) == 3
        assert bars[0].close == 10.5

    def test_meta_records_requested_start_after_download(self, fetcher, mock_xtdata):
        """重新下载后应把本次履约的 requested start 写入 meta,
        下次同样请求才不会再次重拉 (与防风暴测试闭环)。
        """
        symbol = "000001.SZ"
        timeframe = Timeframe.DAY_1
        start_date = "2020-06-15"
        end_date = "2025-12-31"

        # 起点缺口 -> 触发重新下载
        cached_df = pd.DataFrame({
            "datetime": pd.to_datetime(["2024-01-02", "2026-02-13"]),
            "open": [10.0, 11.0], "high": [11.0, 12.0],
            "low": [9.0, 10.0], "close": [10.5, 11.5],
            "volume": [1000, 3000],
        })
        full_ts = [_ms("2022-05-10"), _ms("2025-12-31")]
        df_front = pd.DataFrame({
            "open": [8.0, 14.0], "high": [9.0, 15.0],
            "low": [7.0, 13.0], "close": [8.5, 14.5],
            "volume": [1000, 3000],
        }, index=full_ts)
        df_front.index.name = "datetime"
        df_unadj = pd.DataFrame({"close": [8.8, 14.8]}, index=full_ts)

        with patch("src.infrastructure.gateway.qmt_history_data.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__truediv__.return_value = mock_path.return_value
            with patch("pandas.read_csv", return_value=cached_df):
                with patch("pandas.DataFrame.to_csv"):
                    mock_xtdata.get_market_data_ex.side_effect = [
                        {symbol: df_front},
                        {symbol: df_unadj},
                    ]
                    fetcher.fetch_history_bars(symbol, timeframe, start_date, end_date)

        # 下载后 meta 应记录: 该 symbol 已按 2020-06-15 起完整拉取
        written = mock_path.return_value.write_text.call_args
        assert written is not None, "应写入 _fetch_meta.json"
        saved = json.loads(written[0][0])
        assert saved["000001.SZ_1d"] == "2020-06-15"

    def test_download_exception_logged_not_swallowed(
        self, fetcher, mock_xtdata, mock_to_csv, mock_path, capsys
    ):
        """download_history_data 异常不应被静默吞掉: 打警告后继续走本地数据。"""
        symbol = "000001.SZ"
        ts = [_ms("2023-01-01"), _ms("2023-01-02")]
        df_front = pd.DataFrame({
            "open": [10.0, 10.5], "high": [11.0, 11.5],
            "low": [9.0, 9.5], "close": [10.5, 11.0],
            "volume": [1000, 2000],
        }, index=ts)
        df_front.index.name = "datetime"
        df_unadj = pd.DataFrame({"close": [10.8, 11.2]}, index=ts)

        mock_xtdata.download_history_data.side_effect = RuntimeError("boom")
        mock_xtdata.get_market_data_ex.side_effect = [
            {symbol: df_front},
            {symbol: df_unadj},
        ]

        bars = fetcher.fetch_history_bars(
            symbol, Timeframe.DAY_1, "2023-01-01", "2023-01-02"
        )

        captured = capsys.readouterr()
        assert "download_history_data failed" in captured.out
        assert "boom" in captured.out
        # 异常后仍应继续从本地已有数据取数
        assert len(bars) == 2

    def test_unadjusted_close_failure_logged(
        self, fetcher, mock_xtdata, mock_to_csv, mock_path, capsys
    ):
        """不复权收盘价获取失败不应静默置 0: 打警告并继续返回 bars。"""
        symbol = "000001.SZ"
        ts = [_ms("2023-01-01"), _ms("2023-01-02")]
        df_front = pd.DataFrame({
            "open": [10.0, 10.5], "high": [11.0, 11.5],
            "low": [9.0, 9.5], "close": [10.5, 11.0],
            "volume": [1000, 2000],
        }, index=ts)
        df_front.index.name = "datetime"

        mock_xtdata.get_market_data_ex.side_effect = [
            {symbol: df_front},
            RuntimeError("unadj boom"),
        ]

        bars = fetcher.fetch_history_bars(
            symbol, Timeframe.DAY_1, "2023-01-01", "2023-01-02"
        )

        captured = capsys.readouterr()
        assert "unadjusted close fetch failed" in captured.out
        assert len(bars) == 2
        assert bars[0].unadjusted_close == 0.0
