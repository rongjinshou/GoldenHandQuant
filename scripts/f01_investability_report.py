"""F01 可投性报告数据 — 策略 vs 等权覆盖池基准的 全程/IS/OOS 收益 + 最大回撤。

- 等权覆盖池基准: 每交易日全市场(LAG(close) 日收益)均值复利(对齐重判口径, 设计 DD-3;
  库内 prev_close 恒 0 不可用, 故用 LAG)。
- 策略: 读 backtest_runs 中 source=f01_investability 且非 quick、churn 已修(hold_fix) 的全窗口跑,
  从入库净值曲线 {dates,values} 切 IS(<=split)/OOS(>split) 算收益与回撤。

用法 (Windows python, 仓库根目录): $WIN_PYTHON scripts/f01_investability_report.py
"""

from __future__ import annotations

import json
import os
import sys

import duckdb

sys.path.insert(0, os.getcwd())

DB = "data/market.duckdb"
START, SPLIT, END = "2021-01-01", "2024-06-30", "2026-06-11"


def _ret_mdd(values: list[float]) -> tuple[float, float]:
    """累计收益 + 最大回撤(基于权益序列)。"""
    if len(values) < 2:
        return 0.0, 0.0
    ret = values[-1] / values[0] - 1.0
    peak = values[0]
    mdd = 0.0
    for v in values:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1.0)
    return ret, mdd


def _ew_curve(con, start: str, end: str) -> tuple[list[str], list[float]]:
    """等权覆盖池权益曲线(起点 1.0)。"""
    rows = con.execute(
        """WITH b AS (
               SELECT symbol, date, close,
                      lag(close) OVER (PARTITION BY symbol ORDER BY date) AS pc
               FROM bars WHERE date BETWEEN ? AND ?),
           r AS (SELECT date, close / pc - 1 AS ret FROM b WHERE pc > 0)
           SELECT date, avg(ret) AS d FROM r GROUP BY date ORDER BY date""",
        [start, end],
    ).fetchall()
    dates, vals, cum = [], [], 1.0
    for d, ret in rows:
        cum *= 1 + (ret or 0.0)
        dates.append(str(d))
        vals.append(cum)
    return dates, vals


def _slice(dates: list[str], values: list[float], lo: str, hi: str) -> list[float]:
    return [v for d, v in zip(dates, values) if lo <= d <= hi]


def main() -> None:
    con = duckdb.connect(DB, read_only=True)
    bd, bv = _ew_curve(con, START, END)
    con.close()

    def block(dates, values, label):
        full = _ret_mdd(values)
        is_v = _slice(dates, values, START, SPLIT)
        oos_v = _slice(dates, values, SPLIT, END)
        is_r = _ret_mdd(is_v)
        oos_r = _ret_mdd(oos_v)
        print(f"{label:<22} 全程 {full[0]:+7.1%}(MDD {full[0+1]:6.1%}) | "
              f"IS {is_r[0]:+7.1%}(MDD {is_r[1]:6.1%}) | OOS {oos_r[0]:+7.1%}(MDD {oos_r[1]:6.1%})")

    print(f"窗口 {START} .. {SPLIT}(IS) .. {END}(OOS)\n")
    block(bd, bv, "等权覆盖池基准")

    from src.infrastructure.persistence.market_data_store import MarketDataStore
    st = MarketDataStore(DB, read_only=True)
    try:
        rows = []
        for run in st.load_backtest_runs():
            for s in run["strategies"]:
                p = json.loads(s["params"]) if s.get("params") else {}
                if p.get("source") != "f01_investability" or p.get("quick") or not p.get("hold_fix"):
                    continue
                ec = json.loads(s["equity_curve"]) if s.get("equity_curve") else {}
                d, v = ec.get("dates", []), ec.get("values", [])
                if v:
                    rows.append((p.get("top_n"), s, d, v))
        for top_n, s, d, v in sorted(rows, key=lambda x: x[0] or 0):
            block(d, v, f"MicroValue top_n={top_n}")
            print(f"{'':22} 年化 {s.get('annualized_return'):+.2%} | Sharpe {s.get('sharpe_ratio'):.2f} "
                  f"| 胜率 {s.get('win_rate'):.1%} | 成交 {s.get('trade_count')} | 换手 {s.get('turnover_rate')}")
    finally:
        st.close()


if __name__ == "__main__":
    main()
