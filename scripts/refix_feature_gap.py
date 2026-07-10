"""一次性维护: 修复 stock_features 冷启动 NULL 缺口 (2025-11-25→2026-02-26)。

根因(已复核): 某次增量特征重算时喂给 compute_features 的 bars 缺 200 天预热,
所有滚动窗口在 2025-11-25 边界冷启动产出 NaN; 随后 fetch_meta 标记该区间已履约,
后续 `data refresh` 因 missing_ranges 为空而跳过 → NULL 固化。bars 现已连续覆盖预热区,
强制全历史重算(warmup 从 bars 起点 2020-06-15)即可修复且幂等。

用法:
  python scripts/refix_feature_gap.py                 # 干跑: 仅报告缺口
  python scripts/refix_feature_gap.py --apply --limit 3   # 最小验证: 只重算前 3 只
  python scripts/refix_feature_gap.py --apply             # 全量重算(需先停 dashboard 释放锁)
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.getcwd())

from src.application.market_data_app import MarketDataAppService  # noqa: E402
from src.domain.market.services.feature_engine import FEATURE_VERSION  # noqa: E402
from src.infrastructure.persistence.market_data_store import MarketDataStore  # noqa: E402

DB = "data/market.duckdb"
SOURCE = "qmt"
START = "2021-01-01"   # ws = 2021-01-01 - 200d = 2020-06-15 = bars 起点 → 全历史预热
END = "2026-07-03"     # bars 最大日
GAP_START, GAP_END = "2025-11-25", "2026-02-26"
BASELINE = ("000001.SZ", "2025-06-16")  # 非缺口点, 幂等校验


def _null_gap(conn) -> int:
    return conn.execute(
        f"SELECT COUNT(*) FROM stock_features WHERE feature_version={FEATURE_VERSION} "
        f"AND date BETWEEN DATE '{GAP_START}' AND DATE '{GAP_END}' AND return_20d IS NULL"
    ).fetchone()[0]


def _baseline(conn) -> tuple:
    return conn.execute(
        f"SELECT return_20d, ma_20, rsi_14 FROM stock_features "
        f"WHERE feature_version={FEATURE_VERSION} AND symbol='{BASELINE[0]}' AND date=DATE '{BASELINE[1]}'"
    ).fetchone()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真写库(否则仅报告)")
    ap.add_argument("--limit", type=int, default=0, help="只重算前 N 只(0=全部, 供最小验证)")
    args = ap.parse_args()

    store = MarketDataStore(DB, read_only=not args.apply)
    try:
        conn = store._conn
        symbols = [r[0] for r in conn.execute(
            f"SELECT DISTINCT symbol FROM bars WHERE source='{SOURCE}' ORDER BY symbol"
        ).fetchall()]
        if args.limit:
            symbols = symbols[: args.limit]

        print(f"宇宙: {len(symbols)} 只; 特征版本 v{FEATURE_VERSION}; 区间 [{START}, {END}]")
        print(f"缺口 NULL return_20d 行数(改前): {_null_gap(conn):,}")
        print(f"幂等基线 {BASELINE[0]}@{BASELINE[1]}(改前): {_baseline(conn)}")

        if not args.apply:
            print("\n[干跑] 未写库。加 --apply 执行重算。")
            return

        svc = MarketDataAppService(store, history_fetcher=None, fundamental_fetcher=None, source=SOURCE)  # type: ignore[arg-type]
        n = svc.ensure_features(symbols, START, END, bars_refreshed=set(symbols))
        print(f"\n[已重算] {n} 只特征已 INSERT OR REPLACE 覆盖。")
        print(f"缺口 NULL return_20d 行数(改后): {_null_gap(conn):,}")
        print(f"幂等基线 {BASELINE[0]}@{BASELINE[1]}(改后): {_baseline(conn)}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
