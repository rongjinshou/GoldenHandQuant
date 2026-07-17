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


def resolve_fetcher_type(configured: str, *, force_online: bool = False) -> str:
    """取数命令(data refresh)强制在线 fetcher。

    2026-07-15 数据断流复盘: backtest.yaml 为 F01 离线回测切 DuckDBHistoryDataFetcher
    后, 共用该配置的 data refresh 变成离线空跑(缺口按空返回、退出码 0), 个股日线
    静默断流 3 个交易日。"补数"语义下离线读库桩是谎言 → refresh 一律还原 QMT。
    """
    if force_online and configured == "DuckDBHistoryDataFetcher":
        return "QmtHistoryDataFetcher"
    return configured


@dataclass(slots=True, kw_only=True)
class DataWiring:
    store: MarketDataStore
    market_data: MarketDataAppService
    history_fetcher: object
    fundamental_fetcher: object
    source: str
    config_symbols: list[str]


def build_data_wiring(
    config_path: str, db_path: str = DEFAULT_DB_PATH, *, force_online: bool = False
) -> DataWiring:
    """按配置组装 fetcher（QMT/Tushare）+ store + MarketDataAppService。

    force_online: 取数路径(data refresh)置 True — 配置里的离线读库桩还原为 QMT,
    无 xtquant 环境会在取数时显式报错, 而非静默空跑。
    """
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

    resolved = resolve_fetcher_type(fetcher_type, force_online=force_online)
    if resolved != fetcher_type:
        print(f"(refresh 强制在线: {fetcher_type} → {resolved})")
    fetcher_type = resolved

    if fetcher_type == "TushareHistoryDataFetcher":
        from src.infrastructure.gateway.tushare_fundamental_fetcher import TushareFundamentalFetcher
        from src.infrastructure.gateway.tushare_history_data import TushareHistoryDataFetcher

        history_fetcher = TushareHistoryDataFetcher(token=tushare_token)
        fundamental_fetcher = TushareFundamentalFetcher(token=tushare_token)
        source = "tushare"
    elif fetcher_type == "DuckDBHistoryDataFetcher":
        # 离线读库模式(WSL 无 xtquant 也可跑 factor-test 等只读路径, 2026-07-12)。
        # 不开第二个 duckdb 连接(同进程混合 read_only 配置会 ConnectionException)。
        # 取数桩按"空返回"降级: ensure_bars 的 B1 履约诚实逻辑会把上市窗外缺口正常
        # 履约、可疑缺口留警告不履约(下轮在线补)——离线判决以库内数据继续, 不中断。
        class _OfflineNoFetch:
            calls = 0

            def fetch_history_bars(self, *args, **kwargs):
                _OfflineNoFetch.calls += 1
                return []

            def fetch_by_range(self, *args, **kwargs):
                _OfflineNoFetch.calls += 1
                return []

        print("(离线模式: DuckDB 只读, 缺口按空返回降级——如需补数在 Windows 侧 data refresh)")
        history_fetcher = _OfflineNoFetch()
        fundamental_fetcher = _OfflineNoFetch()
        source = "qmt"  # 库内行按 qmt 源读取(离线复用既有数据)
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
