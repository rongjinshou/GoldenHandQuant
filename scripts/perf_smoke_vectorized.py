"""列式向量化引擎·全窗口真实数据性能冒烟(只读 market.duckdb, 无 QMT)。

对照旧对象路径基线(全窗口 F01 ≈ 13min / 12GB 峰值, 单核)。验证 B8 提速。
用法: $WIN_PYTHON scripts/perf_smoke_vectorized.py
"""

import os
import sys
import time

sys.path.insert(0, os.getcwd())

from src.domain.market.services.feature_engine import FEATURE_VERSION  # noqa: E402
from src.domain.strategy.factor_test.panel import FactorPanel  # noqa: E402
from src.domain.strategy.factor_test.vectorized_runner import VectorizedRunner  # noqa: E402
from src.infrastructure.persistence.market_data_store import MarketDataStore  # noqa: E402

START, END, SPLIT, SOURCE = "2021-01-01", "2026-06-13", "2024-06-30", "qmt"


def main() -> None:
    store = MarketDataStore("data/market.duckdb", read_only=True)

    t0 = time.time()
    df = store.load_feature_join_df(None, START, END, FEATURE_VERSION, SOURCE)
    t_load = time.time() - t0
    panel = FactorPanel(df)
    n_rows = len(df)
    n_dates = int(df["date"].nunique()) if n_rows else 0
    n_syms = int(df["symbol"].nunique()) if n_rows else 0
    mem_mb = df.memory_usage(deep=True).sum() / 1e6
    print(f"[load] {n_rows:,} 行 · {n_syms} 股 × {n_dates} 日 · "
          f"DataFrame {mem_mb:,.0f} MB · {t_load:.1f}s")

    if n_rows == 0:
        print("空数据, 跳过。检查 source/窗口。")
        return

    # IS 切片(与 F01 可投性同口径 split)上跑 long_only F01
    is_panel = panel.slice_is(SPLIT) if SPLIT else panel
    t1 = time.time()
    scored = VectorizedRunner().run(
        "0 - log(market_cap)", is_panel, test_period=(START, SPLIT),
        num_layers=5, rebalance_days=1, objective="long_only", cost_rate=0.003,
    )
    t_run = time.time() - t1
    r = scored.report
    print(f"[run ] F01 long_only(IS {START}→{SPLIT}): {t_run:.1f}s")
    print(f"       IC={r.ic_mean:.4f} IR={r.ir:.3f} TopExcess={r.top_excess_return:.2%} "
          f"ExIR={r.excess_ir:.2f} Score={scored.score:.0f}({scored.grade})")
    print(f"[总计] load+run = {t_load + t_run:.1f}s  (旧对象路径基线 ≈ 13min/12GB 单核)")


if __name__ == "__main__":
    main()
