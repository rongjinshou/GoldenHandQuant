"""B1 退市股 akshare 一次性回填 — 2021+ 沪深退市股 bars + fundamental_snapshots(source='akshare')。

用法: $WIN_PYTHON scripts/backfill_delisted_akshare.py [--dry-run] [--limit N] [--since 2021-01-01]
特性: 节流(0.6s/请求)+指数退避×3 | symbol 粒度断点续传(已入库跳过, 可随时中断重跑)
     | qmt 源重叠防御 | 结束打核数报告(覆盖率/市值口径占比)。
设计: docs/feat/0704-b1-delisted-backfill/2026-07-04-b1-delisted-backfill-design.md
"""

import argparse
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.getcwd())

from src.infrastructure.gateway.akshare_delisted_fetcher import (  # noqa: E402
    AkshareDelistedFetcher,
    build_ttm_fundamentals,
    df_to_bars,
)
from src.infrastructure.persistence.market_data_store import MarketDataStore  # noqa: E402

THROTTLE_SECONDS = 0.6


def _retry(fn, *args, what: str = "", retries: int = 3, base_delay: float = 3.0):
    for i in range(retries):
        try:
            return fn(*args)
        except Exception as e:  # noqa: BLE001 — 网络层退避重试, 最终仍抛
            if i == retries - 1:
                raise
            delay = base_delay * (2 ** i)
            print(f"    重试 {i + 1}/{retries - 1} {what} ({type(e).__name__}), 等 {delay:.0f}s")
            time.sleep(delay)
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="只打清单不拉数不写库")
    ap.add_argument("--limit", type=int, default=None, help="只处理前 N 只(调试)")
    ap.add_argument("--since", default="2021-01-01", help="退市日下限")
    ap.add_argument("--db", default="data/market.duckdb")
    args = ap.parse_args()

    fetcher = AkshareDelistedFetcher()
    delisted = _retry(fetcher.fetch_delist_list, args.since, what="清单")
    delisted.sort(key=lambda d: d["symbol"])
    if args.limit:
        delisted = delisted[: args.limit]
    print(f"退市清单({args.since}+): {len(delisted)} 只 "
          f"(SH {sum(1 for d in delisted if d['symbol'].endswith('.SH'))} / "
          f"SZ {sum(1 for d in delisted if d['symbol'].endswith('.SZ'))})")
    if args.dry_run:
        for d in delisted[:20]:
            print(f"  {d['symbol']} {d['name']} 退市 {d['delist_date']:%Y-%m-%d}")
        print("  ..." if len(delisted) > 20 else "")
        return

    store = MarketDataStore(args.db, read_only=False)
    stats = Counter()
    mcap_basis = Counter()
    failures: list[str] = []
    try:
        for i, item in enumerate(delisted, start=1):
            sym = item["symbol"]
            prefix = f"[{i}/{len(delisted)}] {sym} {item['name']}"
            try:
                if not store.load_bars_df([sym], "2000-01-01", "2099-12-31", "akshare").empty:
                    stats["resume_skip"] += 1
                    continue
                if not store.load_bars_df([sym], "2000-01-01", "2099-12-31", "qmt").empty:
                    print(f"{prefix}: qmt 源已有行, 跳过(防双源重复)")
                    stats["qmt_overlap_skip"] += 1
                    continue

                rows = _retry(fetcher.fetch_daily_qfq, sym, what="qfq日线") or []
                time.sleep(THROTTLE_SECONDS)
                if len(rows) < 30:
                    print(f"{prefix}: qfq 日线不足({len(rows)}), 记失败")
                    stats["bars_missing"] += 1
                    failures.append(f"{sym}(bars={len(rows)})")
                    continue
                raw_map, basis = fetcher.fetch_raw_close(sym)
                time.sleep(THROTTLE_SECONDS)
                mcap_basis[basis] += 1

                reports = _retry(fetcher.fetch_reports, sym, what="财报")
                time.sleep(THROTTLE_SECONDS)

                bars = df_to_bars(sym, rows, raw_map)
                store.upsert_bars(bars, source="akshare")
                stats["bars_ok"] += 1

                snaps = build_ttm_fundamentals(
                    symbol=sym, name=item["name"],
                    list_date=item["list_date"].to_pydatetime(),
                    bars=bars, raw_close_by_date=raw_map, **reports,
                )
                if snaps:
                    store.upsert_fundamentals(snaps, source="akshare")
                    stats["fund_ok"] += 1
                else:
                    stats["fund_missing_share"] += 1
                store.upsert_instruments([{
                    "symbol": sym, "name": item["name"],
                    "list_date": item["list_date"].strftime("%Y-%m-%d"),
                    "delist_date": item["delist_date"].strftime("%Y-%m-%d"),
                }], source="akshare")
                if i % 10 == 0:
                    print(f"{prefix}: bars {len(bars)} 根, fund {len(snaps)} 行 [{basis}] "
                          f"(累计 ok {stats['bars_ok']})")
            except Exception as e:  # noqa: BLE001 — 单只失败不停整体, 留痕续跑
                print(f"{prefix}: 失败 {type(e).__name__}: {str(e)[:100]}")
                stats["error"] += 1
                failures.append(f"{sym}({type(e).__name__})")
    finally:
        store.close()

    print("\n=== 回填核数报告 ===")
    print(f"清单 {len(delisted)} | bars 入库 {stats['bars_ok']} | fundamental 入库 {stats['fund_ok']}")
    print(f"断点续传跳过 {stats['resume_skip']} | qmt 重叠跳过 {stats['qmt_overlap_skip']}")
    print(f"日线缺失 {stats['bars_missing']} | 财报缺股本 {stats['fund_missing_share']} | 异常 {stats['error']}")
    print(f"市值口径占比: {dict(mcap_basis)}")
    if failures:
        print(f"失败清单({len(failures)}): {', '.join(failures[:30])}")


if __name__ == "__main__":
    main()
