"""instruments 名称刷新: 用交易所最新名(ts_stock_basic)修 instruments.name 滞后。

背景: 2026-04 戴帽潮 instruments 快照未跟上(C9 观察项)。幂等; 只动在市股(delist NULL)。
用法: python scripts/refresh_instrument_names.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import duckdb  # noqa: E402


def main() -> int:
    con = duckdb.connect("data/market.duckdb")
    con.execute("ATTACH 'data/tushare.duckdb' AS ts (READ_ONLY)")
    try:
        stale = con.execute(
            """SELECT i.symbol, i.name, s.name
               FROM instruments i
               JOIN ts.ts_stock_basic s ON s.ts_code = i.symbol AND s.list_status='L'
               WHERE i.delist_date IS NULL
                 AND replace(i.name,' ','') <> replace(s.name,' ','')
               LIMIT 8""").fetchall()
        n_row = con.execute(
            """UPDATE instruments AS i SET name = s.name
               FROM ts.ts_stock_basic AS s
               WHERE s.ts_code = i.symbol AND s.list_status='L'
                 AND i.delist_date IS NULL
                 AND replace(i.name,' ','') <> replace(s.name,' ','')""").fetchone()
        n = int(n_row[0]) if n_row else 0
    finally:
        con.execute("DETACH ts")
    print(f"instruments 名称刷新: 更新 {n} 只")
    for sym, old, new in stale:
        print(f"  {sym}: {old} → {new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
