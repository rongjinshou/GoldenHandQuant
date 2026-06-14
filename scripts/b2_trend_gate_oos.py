"""B2 严谨化: 趋势闸 关/开 × 样本内/外(split 2024-06-30) 4 格, 判断闸效是否仅样本内躲崩。

OOS(2024-06→2026)多为牛市, 闸阻断 32~40% 天 → 若 OOS-ON << OOS-OFF 说明闸是样本内
躲崩、牛市过度保守; 若 OOS-ON ≥ OOS-OFF 则泛化。一次装载行情, 4 次回测。
用法: $WIN_PYTHON scripts/b2_trend_gate_oos.py
"""

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

CONFIG, TOP_N, SPLIT = "resources/backtest.yaml", 20, "2024-06-30"


def main() -> None:
    s = load_backtest_config(CONFIG)
    start, end, cap = s.backtest.start_date, s.backtest.end_date, s.backtest.initial_capital
    idx = s.risk.system_gate.index_symbol
    tf = Timeframe.DAY_1

    registry, universe = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", start, end, config_symbols=s.backtest.symbols)
    print(f"宇宙 {len(universe)} 只 | {start}..{end} | split {SPLIT} | top_n={TOP_N}")

    mkt = MockMarketGateway()
    fetcher = DuckDBHistoryDataFetcher(fallback=None)
    for sym in universe:
        mkt.load_bars(fetcher.fetch_history_bars(sym, tf, start, end))

    def run(w_start: str, w_end: str) -> object:
        trade = MockTradeGateway(market_gateway=mkt, initial_capital=cap)
        app = BacktestAppService(
            market_gateway=mkt, trade_gateway=trade,
            strategy=create_strategy("micro_value", {"top_n": TOP_N}),
            evaluator=PerformanceEvaluator(), sizer=EqualWeightSizer(n_symbols=TOP_N),
            fundamental_registry=registry, risk_settings=s.risk)
        return app.run_backtest(
            universe, start_date=datetime.strptime(w_start, "%Y-%m-%d"),
            end_date=datetime.strptime(w_end, "%Y-%m-%d"), base_timeframe=tf)[0]

    def show(tag: str, r) -> None:
        print(f">>> {tag}: 收益 {r.total_return:.2%} | 回撤 {r.max_drawdown:.2%} | "
              f"Sharpe {getattr(r, 'sharpe_ratio', float('nan')):.2f} | 成交 {r.trade_count}")

    # OFF (无指数)
    is_off, oos_off = run(start, SPLIT), run(SPLIT, end)
    show("IS  OFF", is_off); show("OOS OFF", oos_off)
    # ON (加指数)
    mkt.load_bars(fetcher.fetch_history_bars(idx, tf, start, end))
    is_on, oos_on = run(start, SPLIT), run(SPLIT, end)
    fetcher.close()
    show("IS  ON ", is_on); show("OOS ON ", oos_on)

    print("\n=== 趋势闸净效应 (ON − OFF) ===")
    print(f"  IS : 收益 {is_on.total_return - is_off.total_return:+.2%} | 回撤 {is_on.max_drawdown - is_off.max_drawdown:+.2%}")
    print(f"  OOS: 收益 {oos_on.total_return - oos_off.total_return:+.2%} | 回撤 {oos_on.max_drawdown - oos_off.max_drawdown:+.2%}")


if __name__ == "__main__":
    main()
