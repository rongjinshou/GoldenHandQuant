"""B2 A/B: 中证1000 趋势闸 关 vs 开 对 F01(MicroValue top20) 的净效应。

同代码/窗口/止损; 唯一差异 = 行情网关是否含指数 bars(无→闸 inert pass_buy=True; 有→闸按
close<MA20 阻断买入)。隔离趋势闸纯效应。只读 market.duckdb。
用法: $WIN_PYTHON scripts/b2_trend_gate_ab.py
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

CONFIG = "resources/backtest.yaml"
TOP_N = 20


def main() -> None:
    s = load_backtest_config(CONFIG)
    start, end, cap = s.backtest.start_date, s.backtest.end_date, s.backtest.initial_capital
    idx = s.risk.system_gate.index_symbol
    tf = Timeframe.DAY_1

    registry, universe = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", start, end, config_symbols=s.backtest.symbols)
    print(f"宇宙 {len(universe)} 只 | {start}..{end} | ¥{cap:,.0f} | top_n={TOP_N} | 指数 {idx}")

    mkt = MockMarketGateway()
    fetcher = DuckDBHistoryDataFetcher(fallback=None)
    for i, sym in enumerate(universe):
        mkt.load_bars(fetcher.fetch_history_bars(sym, tf, start, end))
        if (i + 1) % 1500 == 0:
            print(f"  bars 装载 {i + 1}/{len(universe)}")

    def run(label: str):
        trade = MockTradeGateway(market_gateway=mkt, initial_capital=cap)
        app = BacktestAppService(
            market_gateway=mkt, trade_gateway=trade,
            strategy=create_strategy("micro_value", {"top_n": TOP_N}),
            evaluator=PerformanceEvaluator(), sizer=EqualWeightSizer(n_symbols=TOP_N),
            fundamental_registry=registry, risk_settings=s.risk)
        r = app.run_backtest(
            universe, start_date=datetime.strptime(start, "%Y-%m-%d"),
            end_date=datetime.strptime(end, "%Y-%m-%d"), base_timeframe=tf)[0]
        print(f">>> {label}: 总收益 {r.total_return:.2%} | 年化 {r.annualized_return:.2%} | "
              f"回撤 {r.max_drawdown:.2%} | 胜率 {r.win_rate:.2%} | 成交 {r.trade_count} | "
              f"Sharpe {getattr(r, 'sharpe_ratio', float('nan')):.2f}")
        return r

    off = run("趋势闸 OFF (无指数, inert)")          # mkt 此时无 idx → 闸 pass_buy=True
    mkt.load_bars(fetcher.fetch_history_bars(idx, tf, start, end))  # 加指数 → 闸激活
    on = run("趋势闸 ON  (中证1000 close<MA20 阻断买入)")
    fetcher.close()

    print("\n=== 趋势闸净效应(ON − OFF) ===")
    print(f"  收益 {on.total_return - off.total_return:+.2%} | "
          f"回撤 {on.max_drawdown - off.max_drawdown:+.2%} | 成交 {on.trade_count - off.trade_count:+d}")


if __name__ == "__main__":
    main()
