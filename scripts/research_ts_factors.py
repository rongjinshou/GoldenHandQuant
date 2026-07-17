"""E9 首铲: tushare 新数据域因子第一轮判决(设计 docs/feat/0712-ts-factor-mining)。

纪律: 假设先行/同 P0 硬门槛/同窗同参/一轮一榜(不回调方向重测)/研究-生产隔离
(precomputed_series 研究口子, 不进 KNOWN_FIELDS)。verdict 入库 run_id=RESEARCH-TS-*。
用法: python scripts/research_ts_factors.py   (WSL 离线, 读 market.duckdb + tushare.duckdb)
"""
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from src.application.factor_test_app import FactorTestResult  # noqa: E402
from src.domain.market.services.feature_engine import FEATURE_VERSION  # noqa: E402
from src.domain.strategy.factor_test.factor_catalog import FactorHypothesis  # noqa: E402
from src.domain.strategy.factor_test.panel import FactorPanel  # noqa: E402
from src.domain.strategy.factor_test.vectorized_neutralizer import (  # noqa: E402
    VectorizedNeutralizer,
)
from src.domain.strategy.factor_test.vectorized_runner import VectorizedRunner  # noqa: E402
from src.domain.strategy.factor_test.verdict import judge_factor  # noqa: E402
from src.infrastructure.persistence.market_data_store import MarketDataStore  # noqa: E402

START, END, SPLIT = "2021-01-01", "2025-12-31", "2024-06-30"
TS_DB = "data/tushare.duckdb"

# (factor_id, 名称, 面板列, 方向, 假设依据) —— 方向在看结果前定死(设计 §二)
RESEARCH_FACTORS = [
    ("R01", "主力净流强度20d", "mf_lg_net20", +1, "主力持续吸筹的价格压力传导"),
    ("R02", "散户净流反向20d", "mf_sm_net20", -1, "散户资金流反向指标"),
    ("R03", "股息率", "dv_ttm", +1, "现金回报溢价/质量代理"),
    ("R04", "低自由流通换手20d", "to_f20", -1, "低换手溢价(自由流通口径)"),
    ("R05", "龙虎榜规避60d", "tl_cnt60", -1, "博彩性/过度关注股回避"),
    ("R06", "低量比5d", "vr5", -1, "短期过热反转"),
]

_RESEARCH_SQL = """
WITH mf AS (
  SELECT ts_code AS symbol, strptime(trade_date,'%Y%m%d')::DATE AS date,
         buy_lg_amount+buy_elg_amount-sell_lg_amount-sell_elg_amount AS lg_net,
         buy_sm_amount-sell_sm_amount AS sm_net,
         buy_sm_amount+sell_sm_amount+buy_md_amount+sell_md_amount
           +buy_lg_amount+sell_lg_amount+buy_elg_amount+sell_elg_amount AS tot
  FROM ts_moneyflow WHERE trade_date BETWEEN '20201101' AND '20251231'
), mfr AS (
  SELECT symbol, date,
         SUM(lg_net) OVER w / NULLIF(SUM(tot) OVER w, 0) AS mf_lg_net20,
         SUM(sm_net) OVER w / NULLIF(SUM(tot) OVER w, 0) AS mf_sm_net20
  FROM mf WINDOW w AS (PARTITION BY symbol ORDER BY date ROWS 19 PRECEDING)
), tl AS (
  SELECT ts_code AS symbol, strptime(trade_date,'%Y%m%d')::DATE AS date, 1 AS hit
  FROM ts_top_list WHERE trade_date BETWEEN '20200901' AND '20251231'
  GROUP BY 1, 2
), db AS (
  SELECT d.ts_code AS symbol, strptime(d.trade_date,'%Y%m%d')::DATE AS date,
         d.dv_ttm,
         AVG(d.turnover_rate_f) OVER w20 AS to_f20,
         AVG(d.volume_ratio)    OVER w5  AS vr5
  FROM ts_daily_basic d WHERE d.trade_date BETWEEN '20200901' AND '20251231'
  WINDOW w20 AS (PARTITION BY d.ts_code ORDER BY d.trade_date ROWS 19 PRECEDING),
         w5  AS (PARTITION BY d.ts_code ORDER BY d.trade_date ROWS 4 PRECEDING)
), spine AS (
  SELECT db.*, COALESCE(tl.hit, 0) AS hit
  FROM db LEFT JOIN tl USING (symbol, date)
)
SELECT s.symbol, s.date, s.dv_ttm, s.to_f20, s.vr5,
       SUM(s.hit) OVER w60 AS tl_cnt60,
       m.mf_lg_net20, m.mf_sm_net20
FROM spine s LEFT JOIN mfr m USING (symbol, date)
WHERE s.date >= DATE '2021-01-01'
WINDOW w60 AS (PARTITION BY s.symbol ORDER BY s.date ROWS 59 PRECEDING)
"""


def _build_panel(store: MarketDataStore) -> FactorPanel:
    print("[1/3] 主库基础面板(features⋈fundamentals)…", flush=True)
    base = store.load_feature_join_df(None, START, END, FEATURE_VERSION, "qmt")
    base["date"] = pd.to_datetime(base["date"])
    print(f"  基础 {len(base):,} 行 × {base.shape[1]} 列", flush=True)

    print("[2/3] tushare 研究列(资金流/股息/换手/龙虎榜/量比)…", flush=True)
    ts = duckdb.connect(TS_DB, read_only=True)
    research = ts.execute(_RESEARCH_SQL).fetch_df()
    ts.close()
    research["date"] = pd.to_datetime(research["date"])
    print(f"  研究 {len(research):,} 行 × {research.shape[1]} 列", flush=True)

    df = base.merge(research, on=["symbol", "date"], how="left")
    cov = {c: float(df[c].notna().mean()) for c in
           ("mf_lg_net20", "mf_sm_net20", "dv_ttm", "to_f20", "tl_cnt60", "vr5")}
    print("  合并覆盖率:", {k: f"{v:.1%}" for k, v in cov.items()}, flush=True)
    return FactorPanel(df)


def main() -> int:
    store = MarketDataStore("data/market.duckdb")
    panel = _build_panel(store)
    runner, vneu = VectorizedRunner(), VectorizedNeutralizer()
    is_panel, oos_panel = panel.slice_is(SPLIT), panel.slice_oos(SPLIT)

    print("[3/3] 六假设判决(同 P0 硬门槛)…", flush=True)
    results: list[FactorTestResult] = []
    for fid, name, col, direction, why in RESEARCH_FACTORS:
        label = f"research:{'-' if direction < 0 else ''}{col}"
        s_is = direction * pd.to_numeric(is_panel.df[col], errors="coerce")
        s_oos = direction * pd.to_numeric(oos_panel.df[col], errors="coerce")

        is_rep = runner.run(label, is_panel, test_period=(START, SPLIT),
                            precomputed_series=s_is)
        oos_rep = runner.run(label, oos_panel, test_period=(SPLIT, END),
                             precomputed_series=s_oos) if not oos_panel.df.empty else None
        neu = vneu.mean_neutralized_ic(label, is_panel, precomputed_series=s_is)
        verdict = judge_factor(is_rep, oos_report=oos_rep, factor_id=fid,
                               factor_name=name, neutralized_ic=neu,
                               objective="long_short")
        hyp = FactorHypothesis(factor_id=fid, name=name, category="研究:tushare新域",
                               expression=label, direction_note=why,
                               evidence_strength="探索", field_ready=False, priority="R")
        results.append(FactorTestResult(hypothesis=hyp, is_report=is_rep,
                                        oos_report=oos_rep, verdict=verdict))
        print(f"  {fid} {name}: IC={is_rep.ic_mean:.4f} IR={is_rep.ir:.3f} "
              f"L/S={is_rep.long_short_return:.2%} OOS_L/S="
              f"{(oos_rep.long_short_return if oos_rep else float('nan')):.2%} "
              f"中性化|IC|={neu:.4f} → {'PASS' if verdict.passed else 'FAIL'}", flush=True)

    rows = []
    for r in results:
        v = r.verdict
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
    run_id = f"RESEARCH-TS-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_params = {"start": START, "end": END, "split": SPLIT,
                  "rebalance_days": 1, "num_layers": 5, "objective": "long_short",
                  "cost_rate": 0.003, "feature_version": FEATURE_VERSION,
                  "source": "tushare-research(moneyflow/daily_basic/top_list)",
                  "discipline": "假设先行/一轮一榜/OOS定夺(设计 0712-ts-factor-mining)"}
    store.insert_verdicts(run_id, run_params, rows)
    print(f"\nVerdicts persisted (run_id={run_id})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
