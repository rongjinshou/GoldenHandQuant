"""日增量市值同步薄壳: bars 最新交易日的 market_cap ← 时点总市值。

源优先级: tushare daily_basic(需 TUSHARE_TOKEN) → akshare 实时快照(盘后≈收盘)。
双源皆败退出码 1(口径漂移必须显性, 设计 DD-3)。影子盘编排上午段自动调用。
用法: python scripts/sync_market_cap.py [--db data/market.duckdb]
"""
import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import duckdb  # noqa: E402

from src.infrastructure.persistence.cap_regime import sync_latest_market_cap  # noqa: E402


def _fetch_tushare(day: str) -> dict[str, float] | None:
    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        return None
    try:
        import tushare as ts
        pro = ts.pro_api(token)
        pro._DataApi__token = token
        if os.environ.get("TUSHARE_HTTP_URL"):
            pro._DataApi__http_url = os.environ["TUSHARE_HTTP_URL"]
        df = pro.daily_basic(trade_date=day)
        if df is None or df.empty:
            return None
        return {str(r["ts_code"]): float(r["total_mv"]) * 10000.0
                for _, r in df.iterrows() if r.get("total_mv")}
    except Exception as exc:
        print(f"[sync-cap] tushare 失败: {exc!r}"[:120])
        return None


def _fetch_akshare() -> dict[str, float] | None:
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty or "总市值" not in df.columns:
            return None
        out: dict[str, float] = {}
        for _, r in df.iterrows():
            code = str(r["代码"])
            mv = r["总市值"]
            if mv is None or mv != mv:  # NaN
                continue
            suffix = ".SH" if code.startswith(("6",)) else (".BJ" if code.startswith(("4", "8", "9")) else ".SZ")
            out[f"{code}{suffix}"] = float(mv)
        return out or None
    except Exception as exc:
        print(f"[sync-cap] akshare 失败: {exc!r}"[:120])
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="日增量市值同步")
    parser.add_argument("--db", default="data/market.duckdb")
    args = parser.parse_args()
    con = duckdb.connect(args.db)
    try:
        result = sync_latest_market_cap(
            con, fetch_primary=_fetch_tushare, fetch_fallback=_fetch_akshare)
    except RuntimeError as exc:
        print(f"[sync-cap] ✗ {exc}")
        return 1
    print(f"[sync-cap] ✓ {result['day']} 覆写 {result['updated']} 行 (源: {result['source']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
