"""算等权覆盖池基准 + 取 backtest_runs 指标, 供人工写 F01 可投性报告。

等权覆盖池基准 = 每交易日全市场(prev_close>0)个股日收益均值复利(对齐重判'等权覆盖池'口径,
设计 DD-3)。再读 f01_investability 的 backtest_runs 指标并排打印, 供与 +16.5% 上界对照。

用法 (Windows python, 仓库根目录):
    $WIN_PYTHON scripts/f01_investability_report.py
"""

from __future__ import annotations

import json
import os
import sys

import duckdb

sys.path.insert(0, os.getcwd())

DB = "data/market.duckdb"
SPLIT = "2024-06-30"
START, END = "2021-01-01", "2026-06-11"


def _ew_benchmark(con, start: str, end: str) -> tuple[float, int]:
    """等权覆盖池累计收益(区间)。

    用 LAG(close) 算日收益 (库内 prev_close 列恒为 0, 不可用)。每交易日全市场个股
    日收益均值复利 —— 对齐重判'等权覆盖池'基准口径(设计 DD-3)。
    """
    rows = con.execute(
        """WITH b AS (
               SELECT symbol, date, close,
                      lag(close) OVER (PARTITION BY symbol ORDER BY date) AS pc
               FROM bars WHERE date BETWEEN ? AND ?),
           r AS (SELECT date, close / pc - 1 AS ret FROM b WHERE pc > 0)
           SELECT date, avg(ret) AS d FROM r GROUP BY date ORDER BY date""",
        [start, end],
    ).fetchall()
    cum = 1.0
    for _, d in rows:
        cum *= 1 + (d or 0.0)
    return cum - 1.0, len(rows)


def main() -> None:
    con = duckdb.connect(DB, read_only=True)
    full_ret, full_n = _ew_benchmark(con, START, END)
    oos_ret, oos_n = _ew_benchmark(con, SPLIT, END)
    print("== 等权覆盖池基准(对齐重判口径) ==")
    print(f"  全程 {START}..{END}: {full_ret:.2%}  ({full_n} 交易日)")
    print(f"  OOS  {SPLIT}..{END}: {oos_ret:.2%}  ({oos_n} 交易日)")
    con.close()

    print("\n== f01_investability backtest_runs 指标 ==")
    from src.infrastructure.persistence.market_data_store import MarketDataStore

    st = MarketDataStore(DB, read_only=True)
    try:
        for run in st.load_backtest_runs():
            for strat in run["strategies"]:
                params = json.loads(strat["params"]) if strat.get("params") else {}
                if params.get("source") != "f01_investability":
                    continue
                # 通用打印: 除大字段外的所有键值(字段名以实跑 schema 为准)
                shown = {k: v for k, v in strat.items()
                         if k not in ("equity_curve", "trades", "params")}
                print(f"  top_n={params.get('top_n')} window={params.get('window')}: {shown}")
    finally:
        st.close()


if __name__ == "__main__":
    main()
