"""F01 可投性回测驱动 — 全市场离线 MicroValueStrategy, top_n 敏感性, 入库 backtest_runs。

把重判找到的 size edge(OOS Top 超额 +16.5% 乐观上界)放进真实撮合: ¥146k 可建仓、
A 股对称真实成本(佣金万2.5/印花0.5‰/过户/滑点±0.1%/流动性10%)、T+1、等权再平衡,
看 size edge 还剩多少 —— 漏斗毕业闸。全程离线读 market.duckdb, 不触 QMT。

用法 (Windows python, 仓库根目录):
    $WIN_PYTHON scripts/run_f01_investability.py            # 全窗口 + top_n {20,10,30}
    $WIN_PYTHON scripts/run_f01_investability.py --quick    # 仅 OOS 窗口 + top_n=20 (计时冒烟)

每个 top_n 结果入 backtest_runs(驾驶舱回测页可查)。
设计/计划: docs/feat/0613-f01-investability/
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.getcwd())

from src.application.backtest_app import BacktestAppService  # noqa: E402
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator  # noqa: E402
from src.domain.market.value_objects.timeframe import Timeframe  # noqa: E402
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer  # noqa: E402
from src.domain.strategy.registry import create_strategy  # noqa: E402
from src.infrastructure.config.settings import load_backtest_config  # noqa: E402
from src.infrastructure.gateway.duckdb_history_data import DuckDBHistoryDataFetcher  # noqa: E402
from src.infrastructure.mock.mock_market import MockMarketGateway  # noqa: E402
from src.infrastructure.mock.mock_trade import MockTradeGateway  # noqa: E402
from src.interfaces.cli._backtest_wiring import build_backtest_cross_section  # noqa: E402
from src.interfaces.cli.run_backtest import store_backtest_reports  # noqa: E402

CONFIG = "resources/backtest.yaml"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="仅 OOS 窗口(2024-06-30..end) + top_n=20, 计时冒烟用")
    args = ap.parse_args()

    s = load_backtest_config(CONFIG)
    start = "2024-06-30" if args.quick else s.backtest.start_date
    end = s.backtest.end_date
    cap = s.backtest.initial_capital
    idx = s.risk.system_gate.index_symbol if s.risk else None
    top_ns = [20] if args.quick else [20, 10, 30]   # headline=20 先跑先存
    tf = Timeframe.DAY_1

    registry, universe = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", start, end, config_symbols=s.backtest.symbols)
    print(f"宇宙 {len(universe)} 只 | 区间 {start}..{end} | 资金 ¥{cap:,.0f} | top_n {top_ns}")

    # 一次性把 bars 装入共享行情网关(避免 N 次重载 6M 行)
    data_symbols = sorted(set(universe + ([idx] if idx else [])))
    mkt = MockMarketGateway()
    fetcher = DuckDBHistoryDataFetcher(fallback=None)   # 离线; 指数缺 bars → 趋势闸 inert
    try:
        for i, sym in enumerate(data_symbols):
            mkt.load_bars(fetcher.fetch_history_bars(sym, tf, start, end))
            if (i + 1) % 1000 == 0:
                print(f"  bars 装载 {i + 1}/{len(data_symbols)}")
    finally:
        fetcher.close()
    if idx and not mkt.get_recent_bars(idx, tf, 5):
        print(f"⚠ 指数 {idx} 无 bars(离线) → 中证1000 趋势闸 inert(设计 DD-4)。")

    for top_n in top_ns:
        print(f"\n=== MicroValue top_n={top_n} ===")
        trade = MockTradeGateway(market_gateway=mkt, initial_capital=cap)
        app = BacktestAppService(
            market_gateway=mkt, trade_gateway=trade,
            strategy=create_strategy("micro_value", {"top_n": top_n}),
            evaluator=PerformanceEvaluator(),
            sizer=EqualWeightSizer(n_symbols=top_n),       # 显式等权, 否则默认 FixedRatio
            fundamental_registry=registry, risk_settings=s.risk)
        reports = app.run_backtest(
            universe, start_date=datetime.strptime(start, "%Y-%m-%d"),
            end_date=datetime.strptime(end, "%Y-%m-%d"), base_timeframe=tf)
        r = reports[0]
        print(f"  总收益 {r.total_return:.2%} | 年化 {r.annualized_return:.2%} | "
              f"回撤 {r.max_drawdown:.2%} | 胜率 {r.win_rate:.2%} | 成交 {r.trade_count}")
        store_backtest_reports(reports, params={
            "source": "f01_investability", "strategy": "micro_value", "top_n": top_n,
            "universe": len(universe), "window": f"{start}..{end}", "quick": args.quick,
            "hold_fix": True})  # MicroValue 非调仓日维持持仓的 churn 修复后


if __name__ == "__main__":
    main()
