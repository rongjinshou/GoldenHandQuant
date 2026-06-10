"""CLI 共用的数据服务组装 — fetcher 选择 + MarketDataStore + 股票池解析。

factor-test 与 data 子命令共用，避免两份配置/分支逻辑漂移。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.market_data_app import MarketDataAppService
    from src.infrastructure.persistence.market_data_store import MarketDataStore

DEFAULT_DB_PATH = "data/market.duckdb"


@dataclass(slots=True, kw_only=True)
class DataWiring:
    store: MarketDataStore
    market_data: MarketDataAppService
    history_fetcher: object
    fundamental_fetcher: object
    source: str
    config_symbols: list[str]


def build_data_wiring(config_path: str, db_path: str = DEFAULT_DB_PATH) -> DataWiring:
    """按配置组装 fetcher（QMT/Tushare）+ store + MarketDataAppService。"""
    from src.application.market_data_app import MarketDataAppService
    from src.infrastructure.persistence.market_data_store import MarketDataStore

    try:
        from src.infrastructure.config.settings import load_backtest_config
        settings = load_backtest_config(config_path)
        config_symbols = settings.backtest.symbols
        fetcher_type = settings.data.history_fetcher
        tushare_token = settings.data.tushare.token
    except FileNotFoundError:
        print(f"Config not found ({config_path}), using default symbols.")
        config_symbols = ["000021.SZ"]
        fetcher_type = "TushareHistoryDataFetcher"
        tushare_token = None

    if fetcher_type == "TushareHistoryDataFetcher":
        from src.infrastructure.gateway.tushare_fundamental_fetcher import TushareFundamentalFetcher
        from src.infrastructure.gateway.tushare_history_data import TushareHistoryDataFetcher

        history_fetcher = TushareHistoryDataFetcher(token=tushare_token)
        fundamental_fetcher = TushareFundamentalFetcher(token=tushare_token)
        source = "tushare"
    else:
        from src.infrastructure.gateway.qmt_fundamental_fetcher import QmtFundamentalFetcher
        from src.infrastructure.gateway.qmt_history_data import QmtHistoryDataFetcher

        history_fetcher = QmtHistoryDataFetcher()
        fundamental_fetcher = QmtFundamentalFetcher()
        source = "qmt"

    store = MarketDataStore(db_path)
    market_data = MarketDataAppService(
        store, history_fetcher, fundamental_fetcher, source=source
    )
    return DataWiring(
        store=store,
        market_data=market_data,
        history_fetcher=history_fetcher,
        fundamental_fetcher=fundamental_fetcher,
        source=source,
        config_symbols=config_symbols,
    )


def resolve_universe(wiring: DataWiring) -> list[str]:
    """全市场股票池：QMT 在线 → sector 列表并 upsert instruments（离线可复用）；
    离线 → 库内 instruments；都不可用 → 配置 symbols。"""
    if wiring.source == "qmt":
        try:
            from src.infrastructure.gateway.xtquant_client import xtdata as _xt
            full = sorted(set(_xt.get_stock_list_in_sector("沪深A股")))
            if full:
                wiring.store.upsert_instruments(
                    [{"symbol": s, "name": s, "list_date": None, "delist_date": None}
                     for s in full],
                    wiring.source,
                )
                print(f"Universe: 全 A 股 {len(full)} 只 (来自 QMT, 已入库)")
                return full
        except Exception as e:
            print(f"Warning: 无法加载全市场列表 ({e}); 尝试库内 instruments。")
        cached = wiring.store.load_symbols(wiring.source)
        if cached:
            print(f"Universe: 全 A 股 {len(cached)} 只 (库内 instruments, 离线模式)")
            return cached
    return wiring.config_symbols
