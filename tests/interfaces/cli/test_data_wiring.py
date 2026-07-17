"""_data_wiring.resolve_fetcher_type — refresh 强制在线判定（2026-07-15 断流复盘）。"""

from src.interfaces.cli.commands._data_wiring import resolve_fetcher_type


class TestResolveFetcherType:
    def test_refresh_should_force_online_when_config_is_offline_duckdb(self):
        # Arrange: backtest.yaml 为 F01 离线回测配了 DuckDB 读库桩
        configured = "DuckDBHistoryDataFetcher"

        # Act: 取数路径(data refresh)强制在线
        resolved = resolve_fetcher_type(configured, force_online=True)

        # Assert: 还原为 QMT, 不允许"补数"走离线空跑
        assert resolved == "QmtHistoryDataFetcher"

    def test_readonly_paths_should_keep_offline_duckdb(self):
        # Arrange/Act: factor-test 等只读路径不强制
        resolved = resolve_fetcher_type("DuckDBHistoryDataFetcher", force_online=False)

        # Assert: 保持离线读库
        assert resolved == "DuckDBHistoryDataFetcher"

    def test_online_fetchers_should_pass_through_unchanged(self):
        # Arrange/Act/Assert: 在线 fetcher 不受 force_online 影响
        assert resolve_fetcher_type("QmtHistoryDataFetcher", force_online=True) == (
            "QmtHistoryDataFetcher"
        )
        assert resolve_fetcher_type("TushareHistoryDataFetcher", force_online=True) == (
            "TushareHistoryDataFetcher"
        )
