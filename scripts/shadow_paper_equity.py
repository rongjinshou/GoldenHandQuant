"""影子盘纸面净值(0704 真单前置 DD-2) — 只主板 F01+趋势闸 理论净值周度入库。

"如果从影子盘上线日(2026-07-04)起跟着 F01 做, 组合净值到哪了" —— 不造纸面账本
(那是第二套撮合=第二事实来源), 直接复用被 golden 锁定的回测引擎重放, 结果入
backtest_runs(run_id=SHADOW-PAPER-<当日>), 驾驶舱回测页天然可见。
用法: $WIN_PYTHON scripts/shadow_paper_equity.py   (每周二收盘 refresh 后, runbook §5 第⑤步)
窗口早期仅数根 bar, 指标无统计意义 —— 如实入库不装样子; 每周新增一行, 历史周留档可回看漂移。
"""

import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.getcwd())

from src.application.backtest_app import BacktestAppService  # noqa: E402
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator  # noqa: E402
from src.domain.market.value_objects.timeframe import Timeframe  # noqa: E402
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer  # noqa: E402
from src.domain.strategy.registry import create_strategy  # noqa: E402
from src.domain.trade.services.pre_trade_checks import check_symbol_scope  # noqa: E402
from src.infrastructure.config.settings import load_backtest_config  # noqa: E402
from src.infrastructure.gateway.duckdb_history_data import DuckDBHistoryDataFetcher  # noqa: E402
from src.infrastructure.mock.mock_market import MockMarketGateway  # noqa: E402
from src.infrastructure.mock.mock_trade import MockTradeGateway  # noqa: E402
from src.infrastructure.persistence.backtest_run_mapper import build_backtest_run_row  # noqa: E402
from src.infrastructure.persistence.market_data_store import MarketDataStore  # noqa: E402
from src.interfaces.cli._backtest_wiring import build_backtest_cross_section  # noqa: E402

SHADOW_START = "2026-07-04"   # 影子盘阶段1 上线日(0626 阶段1 report)
TOP_N, CAP = 20, 146_000.0    # gate PASS 口径(¥146k 对齐真实账户)
DB = "data/market.duckdb"


def main() -> None:
    end = date.today().isoformat()
    s = load_backtest_config("resources/backtest.yaml")
    idx = s.risk.system_gate.index_symbol
    tf = Timeframe.DAY_1

    # 装配窗口向前多取 1 年: 趋势闸 MA20 与基本面 as-of 需要 warmup 数据
    warmup_start = f"{int(SHADOW_START[:4]) - 1}{SHADOW_START[4:]}"
    registry, universe = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", warmup_start, end, config_symbols=[])
    mb_universe = [sym for sym in universe if check_symbol_scope(sym) is None]
    print(f"只主板 {len(mb_universe)}/{len(universe)} 只 | 纸面窗口 {SHADOW_START}..{end} | "
          f"top{TOP_N} ¥{CAP:,.0f} 闸ON({idx})")

    mkt = MockMarketGateway()
    fetcher = DuckDBHistoryDataFetcher(fallback=None)
    for i, sym in enumerate(mb_universe, start=1):
        mkt.load_bars(fetcher.fetch_history_bars(sym, tf, warmup_start, end))
        if i % 600 == 0:
            print(f"  bars 装载 {i}/{len(mb_universe)}")
    mkt.load_bars(fetcher.fetch_history_bars(idx, tf, warmup_start, end))
    fetcher.close()

    trade = MockTradeGateway(market_gateway=mkt, initial_capital=CAP)
    app = BacktestAppService(
        market_gateway=mkt, trade_gateway=trade,
        strategy=create_strategy("micro_value", {"top_n": TOP_N}),
        evaluator=PerformanceEvaluator(), sizer=EqualWeightSizer(n_symbols=TOP_N),
        fundamental_registry=registry, risk_settings=s.risk)
    report = app.run_backtest(
        mb_universe, start_date=datetime.strptime(SHADOW_START, "%Y-%m-%d"),
        end_date=datetime.strptime(end, "%Y-%m-%d"), base_timeframe=tf)[0]

    run_id = f"SHADOW-PAPER-{end.replace('-', '')}"
    row = build_backtest_run_row(report, run_id=run_id, params={
        "kind": "shadow_paper_equity", "universe": "mainboard",
        "top_n": TOP_N, "trend_gate": "ON", "shadow_start": SHADOW_START,
    })
    store = MarketDataStore(DB, read_only=False)
    try:
        store.insert_backtest_runs([row])
    finally:
        store.close()

    n_days = len(report.dates or [])
    print(f"\n纸面净值 {SHADOW_START}→{end}: {n_days} 个交易日 | "
          f"收益 {report.total_return:+.2%} | 回撤 {report.max_drawdown:.2%} | "
          f"成交 {report.trade_count} 笔")
    if n_days < 20:
        print("(窗口尚短, 指标无统计意义 — 曲线本身即产出)")
    print(f"已入库 backtest_runs: {run_id} (驾驶舱回测页可见)")


if __name__ == "__main__":
    main()
