"""多因子组合检验(离线·列式向量化) — F01 基线 + F20/F21/F22/F27 组件 + F30/F31 合成。

单因子已挖尽; F20/F21/F22/F27 中性化残差 IC 正 → 检验等权合成是否构成可投多因子 edge。
只读 market.duckdb(无 QMT), 走 B8 向量化引擎(秒级), 判决入库 factor_verdicts。
用法: $WIN_PYTHON scripts/run_multifactor_combo.py
"""

import os
import sys
import time

sys.path.insert(0, os.getcwd())

from src.application.factor_test_app import FactorTestAppService  # noqa: E402
from src.domain.market.services.feature_engine import FEATURE_VERSION  # noqa: E402
from src.domain.strategy.factor_test.factor_catalog import resolve_factors  # noqa: E402
from src.domain.strategy.factor_test.panel import FactorPanel  # noqa: E402
from src.infrastructure.persistence.market_data_store import MarketDataStore  # noqa: E402

START, END, SPLIT, SOURCE = "2021-01-01", "2026-06-13", "2024-06-30", "qmt"
FACTORS = "F01,F20,F21,F22,F27,F30,F31"


def _verdict_row(v) -> dict:
    return {
        "factor_id": v.factor_id, "factor_name": v.factor_name, "expression": v.expression,
        "ic_mean": v.ic_mean, "ir": v.ir, "ic_positive_rate": v.ic_positive_rate,
        "monotonicity_score": v.monotonicity_score, "long_short_return": v.long_short_return,
        "score": v.score, "grade": v.grade, "oos_ic_mean": v.oos_ic_mean, "oos_ir": v.oos_ir,
        "oos_long_short_return": v.oos_long_short_return, "objective": v.objective,
        "top_excess_return": v.top_excess_return, "oos_top_excess_return": v.oos_top_excess_return,
        "excess_ir": v.excess_ir, "excess_positive_rate": v.excess_positive_rate,
        "passed": v.passed, "reasons": v.reasons,
    }


def main() -> None:
    store = MarketDataStore("data/market.duckdb", read_only=False)  # 需写 factor_verdicts
    hyps = resolve_factors(FACTORS)

    t0 = time.time()
    df = store.load_feature_join_df(None, START, END, FEATURE_VERSION, SOURCE)
    panel = FactorPanel(df)
    print(f"[load] {len(df):,} 行 · {df['symbol'].nunique()} 股 × {df['date'].nunique()} 日 · {time.time()-t0:.1f}s")

    svc = FactorTestAppService(history_fetcher=None, fundamental_fetcher=None)
    t1 = time.time()
    results = svc.run_batch_panel(
        hyps, panel, test_period=(START, END), split_date=SPLIT,
        num_layers=5, rebalance_days=1, objective="long_only", cost_rate=0.003,
    )
    print(f"[run ] {len(hyps)} 因子 long_only IS/OOS+中性化: {time.time()-t1:.1f}s\n")

    print(f"{'ID':<5}{'Name':<22}{'IC':>8}{'ExIR':>7}{'Mono':>6}{'TopEx':>8}"
          f"{'OOS_Ex':>8}{'NeutIC':>8}{'Verd':>6}")
    print("-" * 86)
    for r in results:
        v = r.verdict
        nic = "" if v.neutralized_ic is None else f"{v.neutralized_ic:>8.4f}"
        print(f"{v.factor_id:<5}{v.factor_name[:21]:<22}{v.ic_mean:>8.4f}{v.excess_ir:>7.2f}"
              f"{v.monotonicity_score:>6.2f}{v.top_excess_return:>8.2%}"
              f"{(v.oos_top_excess_return or 0):>8.2%}{nic:>8}"
              f"{'PASS' if v.passed else 'FAIL':>6}")
    print("-" * 86)
    print(f"PASS: {sum(1 for r in results if r.verdict.passed)}/{len(results)}\n")
    for r in results:
        v = r.verdict
        print(f"[{v.factor_id}] {v.factor_name} — {'PASS' if v.passed else 'FAIL'}")
        for reason in v.reasons:
            print(f"  {reason}")

    run_id = "MFCOMBO-" + START.replace("-", "") + "-" + END.replace("-", "")
    params = {"start": START, "end": END, "split": SPLIT, "objective": "long_only",
              "num_layers": 5, "rebalance_days": 1, "cost_rate": 0.003,
              "feature_version": FEATURE_VERSION, "universe_count": int(df["symbol"].nunique()),
              "store_path": "db", "note": "multifactor combo F30/F31"}
    try:
        rows = [_verdict_row(r.verdict) for r in results]
        store.insert_verdicts(run_id, params, rows)
        print(f"\nVerdicts persisted to factor_verdicts (run_id={run_id})")
    except Exception as e:
        print(f"\nWarning: 判决入库失败 ({e}); 终端输出不受影响。")


if __name__ == "__main__":
    main()
