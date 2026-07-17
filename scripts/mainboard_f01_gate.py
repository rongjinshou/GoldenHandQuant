"""阶段0 gate: 只主板域 F01+趋势闸 是否仍成立(保留防御画像)?

把宇宙限到实盘真实可买域(只主板, 复用 pre_trade_checks.check_symbol_scope 单一事实来源,
不手写前缀), 跑 MicroValue top20 + 中证1000 趋势闸 的 IS/OOS × ON/OFF 四格, 对照只主板
等权覆盖池基准。判据(DD-4): 主板域 OOS 若保留「回撤<只主板等权基准 + 趋势闸 ON 增益不蒸发」
→ pass, 进阶段1(影子盘); 否则 fail, 重议板块。

全市场基线(B2 已知, 同口径对照): 全窗 ON 145%/MDD10.7%/Sharpe1.51; OOS Sharpe 1.73。
用法: $WIN_PYTHON scripts/mainboard_f01_gate.py  (离线, 只读 market.duckdb)
设计: docs/feat/0626-mainboard-f01-shadow/2026-06-26-mainboard-f01-shadow-design.md
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.getcwd())

import duckdb  # noqa: E402

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
from src.infrastructure.persistence.status_registry_loader import (  # noqa: E402
    build_status_registry_from_db,
)
from src.interfaces.cli._backtest_wiring import build_backtest_cross_section  # noqa: E402

CONFIG, TOP_N, SPLIT, DB = "resources/backtest.yaml", 20, "2024-06-30", "data/market.duckdb"


def is_mainboard(symbol: str) -> bool:
    """复用实盘标的范围闸(SH+60 / SZ+000/001), pre_trade_checks 单一事实来源。"""
    return check_symbol_scope(symbol) is None


def _ret_mdd(values: list[float]) -> tuple[float, float]:
    """累计收益 + 最大回撤(基于权益序列)。"""
    if len(values) < 2:
        return 0.0, 0.0
    ret = values[-1] / values[0] - 1.0
    peak, mdd = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1.0)
    return ret, mdd


def _ew_mainboard_curve(con, start: str, end: str) -> tuple[list[str], list[float]]:
    """只主板等权覆盖池权益曲线(LAG(close) 日收益复利; 主板过滤口径同 check_symbol_scope)。"""
    rows = con.execute(
        """WITH b AS (
               SELECT symbol, date, close,
                      lag(close) OVER (PARTITION BY symbol ORDER BY date) AS pc
               FROM bars
               WHERE date BETWEEN ? AND ?
                 AND (symbol LIKE '60%.SH' OR symbol LIKE '000%.SZ' OR symbol LIKE '001%.SZ')),
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
    s = load_backtest_config(CONFIG)
    start, end, cap = s.backtest.start_date, s.backtest.end_date, s.backtest.initial_capital
    idx = s.risk.system_gate.index_symbol
    tf = Timeframe.DAY_1

    registry, universe = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", start, end, config_symbols=s.backtest.symbols)
    mb_universe = [sym for sym in universe if is_mainboard(sym)]
    print(f"全市场 {len(universe)} → 只主板 {len(mb_universe)} 只 | {start}..{end} | "
          f"split {SPLIT} | top_n={TOP_N} | 指数 {idx}")

    mkt = MockMarketGateway()
    fetcher = DuckDBHistoryDataFetcher(fallback=None)
    for sym in mb_universe:
        mkt.load_bars(fetcher.fetch_history_bars(sym, tf, start, end))

    def run(w_start: str, w_end: str):
        status_registry = build_status_registry_from_db(start=w_start, end=w_end)
        trade = MockTradeGateway(market_gateway=mkt, initial_capital=cap,
                                 stock_status_registry=status_registry)
        app = BacktestAppService(
            market_gateway=mkt, trade_gateway=trade,
            strategy=create_strategy("micro_value", {"top_n": TOP_N}),
            evaluator=PerformanceEvaluator(), sizer=EqualWeightSizer(n_symbols=TOP_N),
            fundamental_registry=registry, status_registry=status_registry,
            risk_settings=s.risk)
        return app.run_backtest(
            mb_universe, start_date=datetime.strptime(w_start, "%Y-%m-%d"),
            end_date=datetime.strptime(w_end, "%Y-%m-%d"), base_timeframe=tf)[0]

    def show(tag: str, r) -> None:
        print(f">>> {tag}: 收益 {r.total_return:+7.2%} | 回撤 {r.max_drawdown:7.2%} | "
              f"Sharpe {getattr(r, 'sharpe_ratio', float('nan')):5.2f} | 成交 {r.trade_count}")

    # OFF (mkt 无指数 → 趋势闸 inert pass_buy=True)
    is_off, oos_off = run(start, SPLIT), run(SPLIT, end)
    # ON (加指数 → 闸按 close<MA20 阻断买入)
    mkt.load_bars(fetcher.fetch_history_bars(idx, tf, start, end))
    is_on, oos_on = run(start, SPLIT), run(SPLIT, end)
    fetcher.close()

    # 只主板等权覆盖池基准
    con = duckdb.connect(DB, read_only=True)
    bd, bv = _ew_mainboard_curve(con, start, end)
    con.close()
    b_full, b_is, b_oos = _ret_mdd(bv), _ret_mdd(_slice(bd, bv, start, SPLIT)), _ret_mdd(_slice(bd, bv, SPLIT, end))

    print("\n=== 主板域 F01+趋势闸 四格 ===")
    show("IS  OFF", is_off)
    show("IS  ON ", is_on)
    show("OOS OFF", oos_off)
    show("OOS ON ", oos_on)
    print("\n=== 只主板等权覆盖池基准(costless) ===")
    print(f"  全程 {b_full[0]:+.2%}(MDD {b_full[1]:.2%}) | IS {b_is[0]:+.2%}(MDD {b_is[1]:.2%}) | "
          f"OOS {b_oos[0]:+.2%}(MDD {b_oos[1]:.2%})")
    print("\n=== 趋势闸净效应 (ON − OFF) ===")
    print(f"  IS : 收益 {is_on.total_return - is_off.total_return:+.2%} | "
          f"回撤 {is_on.max_drawdown - is_off.max_drawdown:+.2%} | "
          f"Sharpe {is_on.sharpe_ratio - is_off.sharpe_ratio:+.2f}")
    print(f"  OOS: 收益 {oos_on.total_return - oos_off.total_return:+.2%} | "
          f"回撤 {oos_on.max_drawdown - oos_off.max_drawdown:+.2%} | "
          f"Sharpe {oos_on.sharpe_ratio - oos_off.sharpe_ratio:+.2f}")

    # gate 判据(DD-4)。注: PerformanceEvaluator.max_drawdown 为正幅度, _ret_mdd(基准) 为
    # 负值 → 比较统一取绝对幅度, 避免跨符号误判。
    crit1 = oos_on.max_drawdown < abs(b_oos[1])  # F01 OOS 回撤幅度比基准浅(更优)
    # crit2: 趋势闸 OOS 增益不蒸发(Sharpe↑ 且 回撤↓, 均为正幅度)
    crit2 = (oos_on.sharpe_ratio > oos_off.sharpe_ratio) and (oos_on.max_drawdown < oos_off.max_drawdown)
    v1, v2 = ('✅' if crit1 else '❌'), ('✅' if crit2 else '❌')
    verdict = 'PASS — 防御画像保留, 进阶段1' if crit1 and crit2 else 'FAIL — 重议板块(人工复核)'
    print("\n=== gate 判据 (DD-4) ===")
    print(f"  ① OOS 回撤幅度优于只主板等权基准: {oos_on.max_drawdown:.2%} vs {abs(b_oos[1]):.2%} → {v1}")
    print(f"  ② 趋势闸 OOS 增益不蒸发(Sharpe↑ 且 回撤↓ vs OFF): → {v2}")
    print(f"  初步裁定: {verdict}")


if __name__ == "__main__":
    main()
