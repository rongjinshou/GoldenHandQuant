"""回测截面策略的数据装配 — 三个回测入口(run_backtest/quant backtest/compare)共用。

统一前: 三入口各写一份, 其中两个把宇宙随机截到 500(对 micro-cap=静默错误结论)。
统一后: 一处修复, 三入口同口径, 去截断; DuckDB 源全离线全市场。
设计: docs/feat/0613-f01-investability/2026-06-13-f01-investability-design.md DD-2
"""

from __future__ import annotations

from src.domain.market.services.fundamental_registry import FundamentalRegistry

DEFAULT_DB_PATH = "data/market.duckdb"


def build_backtest_cross_section(
    history_fetcher_type: str,
    start_date: str,
    end_date: str,
    *,
    tushare_token: str | None = None,
    config_symbols: list[str] | None = None,
    db_path: str = DEFAULT_DB_PATH,
    max_universe: int | None = None,
    include_sources: tuple[str, ...] = ("qmt",),
) -> tuple[FundamentalRegistry, list[str]]:
    """返回 (fundamental_registry, stock_universe)。

    - DuckDBHistoryDataFetcher: 基本面 + 宇宙全部来自 market.duckdb(离线全市场, 无截断)。
    - TushareHistoryDataFetcher: Tushare 基本面, 其覆盖标的为宇宙。
    - 其它(QMT): QMT 基本面 + 沪深A股 sector 为宇宙(去随机500截断; max_universe 显式限速)。
    """
    registry = FundamentalRegistry()

    if history_fetcher_type == "DuckDBHistoryDataFetcher":
        from src.infrastructure.gateway.duckdb_fundamental_fetcher import DuckDBFundamentalFetcher
        from src.infrastructure.persistence.market_data_store import MarketDataStore

        store = MarketDataStore(db_path, read_only=True)
        try:
            universe = store.load_symbols(include_sources)
        finally:
            store.close()
        if max_universe is not None and len(universe) > max_universe:
            universe = sorted(universe)[:max_universe]

        fetcher = DuckDBFundamentalFetcher(db_path)
        try:
            snapshots = fetcher.fetch_by_range(start_date, end_date, symbols=universe)
        finally:
            fetcher.close()
        registry.load_snapshots(snapshots)
        universe = sorted({s.symbol for s in snapshots})
        print(f"Universe(DuckDB 离线): {len(universe)} 只, 基本面 {len(snapshots)} 条")
        return registry, universe

    if history_fetcher_type == "TushareHistoryDataFetcher":
        from src.infrastructure.gateway.tushare_fundamental_fetcher import TushareFundamentalFetcher

        snapshots = TushareFundamentalFetcher(token=tushare_token).fetch_by_range(start_date, end_date)
        registry.load_snapshots(snapshots)
        return registry, sorted({s.symbol for s in snapshots})

    # QMT 在线
    from src.infrastructure.gateway.qmt_fundamental_fetcher import QmtFundamentalFetcher

    universe: list[str] = []
    try:
        from src.infrastructure.gateway.xtquant_client import xtdata as _xt

        for sector in ["沪深A股"]:
            universe.extend(_xt.get_stock_list_in_sector(sector))
    except Exception as e:  # noqa: BLE001 — QMT 不可用时降级, 不阻塞
        print(f"Warning: 无法加载全市场列表 ({e})")
    universe = sorted(set(universe))
    if max_universe is not None and len(universe) > max_universe:
        universe = universe[:max_universe]
    snapshots = QmtFundamentalFetcher().fetch_by_range(start_date, end_date, symbols=universe or None)
    registry.load_snapshots(snapshots)
    return registry, sorted({s.symbol for s in snapshots})
