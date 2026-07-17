"""交易所日历同步 → market.duckdb `trade_calendar`(0711 tushare 沉淀·兑现①)。

一次同步含未来节假日安排(交易所年末公布次年日历), 使 TradingCalendar 与影子盘
仪表获得前瞻能力(未来周二可预判 EXEMPT)。年度维护: 每年 12 月重跑一次即可。

用法(需 TUSHARE_TOKEN, 可选 TUSHARE_HTTP_URL):
  set -a; . <env>; set +a
  python scripts/sync_trade_calendar.py [--start 2015-01-01]
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.infrastructure.persistence.market_data_store import MarketDataStore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="交易所日历同步")
    ap.add_argument("--db", default="data/market.duckdb")
    ap.add_argument("--start", default="2015-01-01")
    args = ap.parse_args()

    import tushare as ts

    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        raise SystemExit("缺 TUSHARE_TOKEN 环境变量")
    pro = ts.pro_api(token)
    pro._DataApi__token = token
    if os.environ.get("TUSHARE_HTTP_URL"):
        pro._DataApi__http_url = os.environ["TUSHARE_HTTP_URL"]

    # end 不设上限: 交易所公布到哪拉到哪(通常至当年末/次年末)
    df = pro.trade_cal(exchange="SSE", start_date=args.start.replace("-", ""),
                       end_date="20991231")
    rows = [(datetime.strptime(str(r["cal_date"]), "%Y%m%d").date(), int(r["is_open"]) == 1)
            for _, r in df.iterrows()]
    store = MarketDataStore(args.db)
    n = store.save_trade_calendar(rows, source="tushare_sse")
    open_n = sum(1 for _, o in rows if o)
    print(f"trade_calendar 入库 {n} 天(开市 {open_n}), 已知至 {max(d for d, _ in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
