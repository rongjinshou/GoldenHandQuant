"""B2: 抓中证1000(000852.SH)指数 bars 入库 market.duckdb → 让离线回测趋势闸生效。

需 QMT 交易端在线(极简模式)。只抓指数 bars(不算特征, 趋势闸只用 bars)。
用法: $WIN_PYTHON scripts/fetch_index_bars.py
"""

import os
import sys

sys.path.insert(0, os.getcwd())

from src.application.market_data_app import MarketDataAppService  # noqa: E402
from src.infrastructure.gateway.qmt_fundamental_fetcher import QmtFundamentalFetcher  # noqa: E402
from src.infrastructure.gateway.qmt_history_data import QmtHistoryDataFetcher  # noqa: E402
from src.infrastructure.persistence.market_data_store import MarketDataStore  # noqa: E402

INDEX = "000852.SH"
START, END = "2020-06-01", "2026-06-13"   # 含 warmup, 覆盖回测窗


def main() -> None:
    store = MarketDataStore("data/market.duckdb", read_only=False)
    svc = MarketDataAppService(
        store, QmtHistoryDataFetcher(), QmtFundamentalFetcher(), source="qmt"
    )
    refreshed = svc.ensure_bars([INDEX], START, END)
    print(f"ensure_bars 刷新: {refreshed}")

    row = store._conn.execute(
        "SELECT count(*), min(date), max(date) FROM bars WHERE symbol=?", [INDEX]
    ).fetchone()
    print(f"{INDEX} bars 入库: {row[0]} 根, {row[1]} → {row[2]}")


if __name__ == "__main__":
    main()
