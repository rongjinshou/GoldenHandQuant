"""E9 第二轮: 2010-2019 独立窗口复验(设计 0712-ts-factor-mining §一.4 多重检验纪律)。

面板完全出自 tushare 自洽宇宙(后复权收益=raw close×adj_factor, 消除除权跳变;
市值/换手/资金流/龙虎榜同源)——与第一轮(主库面板)数据体系独立。
六假设原样重测, 决策判据只对第一轮过闸者(R04)生效: 双窗皆过才谈晋升。
用法: python scripts/research_ts_factors_reval.py
"""
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from src.domain.strategy.factor_test.panel import FactorPanel  # noqa: E402
from src.domain.strategy.factor_test.vectorized_neutralizer import (  # noqa: E402
    VectorizedNeutralizer,
)
from src.domain.strategy.factor_test.vectorized_runner import VectorizedRunner  # noqa: E402
from src.domain.strategy.factor_test.verdict import judge_factor  # noqa: E402
from src.infrastructure.persistence.market_data_store import MarketDataStore  # noqa: E402

START, END, SPLIT = "2010-06-01", "2019-12-31", "2016-06-30"
TS_DB = "data/tushare.duckdb"

RESEARCH_FACTORS = [  # 与第一轮完全一致(scripts/research_ts_factors.py)
    ("R01", "主力净流强度20d", "mf_lg_net20", +1, "主力持续吸筹的价格压力传导"),
    ("R02", "散户净流反向20d", "mf_sm_net20", -1, "散户资金流反向指标"),
    ("R03", "股息率", "dv_ttm", +1, "现金回报溢价/质量代理"),
    ("R04", "低自由流通换手20d", "to_f20", -1, "低换手溢价(自由流通口径)"),
    ("R05", "龙虎榜规避60d", "tl_cnt60", -1, "博彩性/过度关注股回避"),
    ("R06", "低量比5d", "vr5", -1, "短期过热反转"),
]

_PANEL_SQL = """
WITH px AS (
  SELECT d.ts_code AS symbol, strptime(d.trade_date,'%Y%m%d')::DATE AS date,
         d.close * a.adj_factor AS exec_close
  FROM ts_daily d
  JOIN ts_adj_factor a ON a.ts_code = d.ts_code AND a.trade_date = d.trade_date
  WHERE d.trade_date BETWEEN '20091001' AND '20191231' AND d.close > 0 AND a.adj_factor > 0
), pxr AS (
  SELECT symbol, date, exec_close,
         exec_close / NULLIF(LAG(exec_close, 20) OVER (PARTITION BY symbol ORDER BY date), 0) - 1
           AS return_20d
  FROM px
), mf AS (
  SELECT ts_code AS symbol, strptime(trade_date,'%Y%m%d')::DATE AS date,
         buy_lg_amount+buy_elg_amount-sell_lg_amount-sell_elg_amount AS lg_net,
         buy_sm_amount-sell_sm_amount AS sm_net,
         buy_sm_amount+sell_sm_amount+buy_md_amount+sell_md_amount
           +buy_lg_amount+sell_lg_amount+buy_elg_amount+sell_elg_amount AS tot
  FROM ts_moneyflow WHERE trade_date BETWEEN '20091001' AND '20191231'
), mfr AS (
  SELECT symbol, date,
         SUM(lg_net) OVER w / NULLIF(SUM(tot) OVER w, 0) AS mf_lg_net20,
         SUM(sm_net) OVER w / NULLIF(SUM(tot) OVER w, 0) AS mf_sm_net20
  FROM mf WINDOW w AS (PARTITION BY symbol ORDER BY date ROWS 19 PRECEDING)
), tl AS (
  SELECT ts_code AS symbol, strptime(trade_date,'%Y%m%d')::DATE AS date, 1 AS hit
  FROM ts_top_list WHERE trade_date BETWEEN '20091001' AND '20191231'
  GROUP BY 1, 2
), db AS (
  SELECT d.ts_code AS symbol, strptime(d.trade_date,'%Y%m%d')::DATE AS date,
         d.total_mv * 10000.0 AS market_cap, d.dv_ttm,
         AVG(d.turnover_rate_f) OVER w20 AS to_f20,
         AVG(d.volume_ratio)    OVER w5  AS vr5
  FROM ts_daily_basic d WHERE d.trade_date BETWEEN '20091001' AND '20191231'
  WINDOW w20 AS (PARTITION BY d.ts_code ORDER BY d.trade_date ROWS 19 PRECEDING),
         w5  AS (PARTITION BY d.ts_code ORDER BY d.trade_date ROWS 4 PRECEDING)
), spine AS (
  SELECT p.symbol, p.date, p.exec_close, p.return_20d,
         b.market_cap, b.dv_ttm, b.to_f20, b.vr5,
         COALESCE(t.hit, 0) AS hit
  FROM pxr p
  JOIN db b USING (symbol, date)
  LEFT JOIN tl t USING (symbol, date)
)
SELECT s.*, SUM(s.hit) OVER w60 AS tl_cnt60,
       m.mf_lg_net20, m.mf_sm_net20
FROM spine s LEFT JOIN mfr m USING (symbol, date)
WHERE s.date >= DATE '2010-06-01'
WINDOW w60 AS (PARTITION BY s.symbol ORDER BY s.date ROWS 59 PRECEDING)
"""


def main() -> int:
    print("[1/2] tushare 自洽面板(2010-2019, 后复权收益)…", flush=True)
    ts = duckdb.connect(TS_DB, read_only=True)
    df = ts.execute(_PANEL_SQL).fetch_df()
    ts.close()
    df["date"] = pd.to_datetime(df["date"])
    print(f"  面板 {len(df):,} 行 | 股票 {df['symbol'].nunique()} | "
          f"{df['date'].min().date()}→{df['date'].max().date()}", flush=True)
    panel = FactorPanel(df)
    is_panel, oos_panel = panel.slice_is(SPLIT), panel.slice_oos(SPLIT)

    print("[2/2] 六假设独立窗口复验…", flush=True)
    runner, vneu = VectorizedRunner(), VectorizedNeutralizer()
    rows = []
    for fid, name, col, direction, why in RESEARCH_FACTORS:
        label = f"reval2010s:{'-' if direction < 0 else ''}{col}"
        s_is = direction * pd.to_numeric(is_panel.df[col], errors="coerce")
        s_oos = direction * pd.to_numeric(oos_panel.df[col], errors="coerce")
        is_rep = runner.run(label, is_panel, test_period=(START, SPLIT),
                            precomputed_series=s_is)
        oos_rep = runner.run(label, oos_panel, test_period=(SPLIT, END),
                             precomputed_series=s_oos)
        neu = vneu.mean_neutralized_ic(label, is_panel, precomputed_series=s_is)
        v = judge_factor(is_rep, oos_report=oos_rep, factor_id=fid, factor_name=name,
                         neutralized_ic=neu, objective="long_short")
        rows.append({
            "factor_id": v.factor_id, "factor_name": v.factor_name,
            "expression": v.expression, "ic_mean": v.ic_mean, "ir": v.ir,
            "ic_positive_rate": v.ic_positive_rate,
            "monotonicity_score": v.monotonicity_score,
            "long_short_return": v.long_short_return,
            "score": v.score, "grade": v.grade,
            "oos_ic_mean": v.oos_ic_mean, "oos_ir": v.oos_ir,
            "oos_long_short_return": v.oos_long_short_return,
            "objective": v.objective,
            "top_excess_return": v.top_excess_return,
            "oos_top_excess_return": v.oos_top_excess_return,
            "excess_ir": v.excess_ir, "excess_positive_rate": v.excess_positive_rate,
            "passed": v.passed, "reasons": v.reasons,
        })
        print(f"  {fid} {name}: IC={is_rep.ic_mean:.4f} IR={is_rep.ir:.3f} "
              f"L/S={is_rep.long_short_return:.2%} OOS_L/S={oos_rep.long_short_return:.2%} "
              f"中性化|IC|={neu:.4f} → {'PASS' if v.passed else 'FAIL'}", flush=True)

    store = MarketDataStore("data/market.duckdb")
    run_id = f"RESEARCH-TS-REVAL2010S-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    store.insert_verdicts(run_id, {
        "start": START, "end": END, "split": SPLIT,
        "rebalance_days": 1, "num_layers": 5, "objective": "long_short",
        "cost_rate": 0.003, "source": "tushare-selfconsistent-panel(hfq)",
        "purpose": "独立窗口复验(多重检验纪律), 决策判据仅对第一轮过闸者 R04 生效",
    }, rows)
    print(f"\nVerdicts persisted (run_id={run_id})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
