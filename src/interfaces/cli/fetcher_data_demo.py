"""
QmtFundamentalFetcher 数据演示脚本。

使用方式:
    python -m src.interfaces.cli.fetcher_data_demo

前提: QMT 客户端已启动。
"""

import os
import sys
from collections import Counter
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from src.infrastructure.gateway.qmt_fundamental_fetcher import QmtFundamentalFetcher


def separator(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def main():
    fetcher = QmtFundamentalFetcher()

    symbols = ['002284.SZ', '002648.SZ']
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    # ================================================================
    # 1. fetch_by_range — 基本面快照
    # ================================================================
    separator("1. fetch_by_range — 基本面快照")

    snapshots = fetcher.fetch_by_range(
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
    )

    print(f"总快照数: {len(snapshots)}")
    print(f"标的数:   {len(set(s.symbol for s in snapshots))}")
    print(f"交易日数: {len(set(s.date for s in snapshots))}")

    # 按股票汇总
    sym_counts = Counter(s.symbol for s in snapshots)
    print(f"\n每只股票快照数: {dict(sym_counts)}")

    # 展示全部快照
    separator("2. 全部快照明细")

    print(f"{'symbol':12s} {'date':12s} {'name':8s} {'list_date':12s} "
          f"{'mcap(亿)':>10s} {'roe':>10s} {'ocf':>10s}")
    print("-" * 80)

    for s in snapshots:
        mcap_yi = s.market_cap / 1e8
        roe_str = f"{s.roe_ttm:.4f}" if s.roe_ttm is not None else "None"
        ocf_str = f"{s.ocf_ttm:.4f}" if s.ocf_ttm is not None else "None"
        print(f"{s.symbol:12s} {s.date.strftime('%Y-%m-%d'):12s} {s.name:8s} "
              f"{s.list_date.strftime('%Y-%m-%d'):12s} "
              f"{mcap_yi:10.1f} {roe_str:>10s} {ocf_str:>10s}")

    # 每只股票首尾对比
    separator("3. 每只股票首尾对比")

    for sym in sorted(sym_counts):
        syms = [s for s in snapshots if s.symbol == sym]
        first, last = syms[0], syms[-1]
        print(f"\n{sym} ({first.name})")
        print(f"  上市日期: {first.list_date.strftime('%Y-%m-%d')}")
        print(f"  {'':4s} {'日期':12s} {'市值(亿)':>10s} {'ROE':>10s} {'OCF':>10s}")
        print(f"  首日 {first.date.strftime('%Y-%m-%d'):12s} "
              f"{first.market_cap/1e8:10.1f} "
              f"{first.roe_ttm if first.roe_ttm is not None else 'N/A':>10} "
              f"{first.ocf_ttm if first.ocf_ttm is not None else 'N/A':>10}")
        print(f"  末日 {last.date.strftime('%Y-%m-%d'):12s} "
              f"{last.market_cap/1e8:10.1f} "
              f"{last.roe_ttm if last.roe_ttm is not None else 'N/A':>10} "
              f"{last.ocf_ttm if last.ocf_ttm is not None else 'N/A':>10}")

    # ================================================================
    # 4. fetch_index_daily — 指数日线
    # ================================================================
    separator("4. fetch_index_daily — 指数日线 (000852.SH)")

    index_data = fetcher.fetch_index_daily('000852.SH', start_date, end_date)
    print(f"返回条数: {len(index_data)}")

    if index_data:
        print(f"\n{'date':12s} {'open':>10s} {'high':>10s} {'low':>10s} {'close':>10s} {'volume':>15s}")
        print("-" * 70)
        for row in index_data[:10]:
            print(f"{row['trade_date']:12s} "
                  f"{row['open']:10.2f} {row['high']:10.2f} "
                  f"{row['low']:10.2f} {row['close']:10.2f} "
                  f"{row['volume']:15.0f}")
        if len(index_data) > 10:
            print(f"... 共 {len(index_data)} 条，仅显示前 10 条")

    separator("DONE")


if __name__ == "__main__":
    main()
