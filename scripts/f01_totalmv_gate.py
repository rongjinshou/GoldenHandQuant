"""MC-1 决策仪器: 总市值口径版 F01+趋势闸 gate 重验(方案 C 的离线腿)。

与 mainboard_f01_gate.py 逐行同构, **唯一自由变量 = market_cap 来源**:
QMT 股本口径(现状) → tushare `ts_daily_basic.total_mv`(时点正确总市值, 2026-07-12 沉淀)。
其余(ST 注册表/名称修正/趋势闸/成本/宇宙/split)完全一致 —— 差异可全部归因口径。

用法: python scripts/f01_totalmv_gate.py   (离线; 读 market.duckdb + tushare.duckdb)
背景: docs/rules/debt-ledger.md MC-1 / docs/feat/0711-tushare-asset/
"""

import os
import sys
from dataclasses import replace
from datetime import datetime

sys.path.insert(0, os.getcwd())

import duckdb  # noqa: E402

from src.application.backtest_app import BacktestAppService  # noqa: E402
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator  # noqa: E402
from src.domain.market.services.fundamental_registry import FundamentalRegistry  # noqa: E402
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

CONFIG, TOP_N, SPLIT = "resources/backtest.yaml", 20, "2024-06-30"
DB, TS_DB = "data/market.duckdb", "data/tushare.duckdb"


def is_mainboard(symbol: str) -> bool:
    return check_symbol_scope(symbol) is None


def _load_totalmv_map(start: str, end: str) -> dict[str, dict[datetime, float]]:
    """tushare 时点总市值(元), 只取主板窗口内。{symbol: {snapshot_date: mv}}"""
    con = duckdb.connect(TS_DB, read_only=True)
    rows = con.execute(
        """SELECT ts_code, trade_date, total_mv * 10000.0
           FROM ts_daily_basic
           WHERE trade_date BETWEEN ? AND ? AND total_mv > 0
             AND (ts_code LIKE '60%.SH' OR ts_code LIKE '000%.SZ' OR ts_code LIKE '001%.SZ')""",
        [start.replace("-", ""), end.replace("-", "")],
    ).fetchall()
    con.close()
    out: dict[str, dict[datetime, float]] = {}
    for sym, d, mv in rows:
        day = datetime(int(d[:4]), int(d[4:6]), int(d[6:8]))
        out.setdefault(sym, {})[day] = float(mv)
    return out


def _override_registry(registry, mv_map) -> tuple[FundamentalRegistry, int, int]:
    """重建注册表: 主板快照的 market_cap 换成时点总市值; 无覆写数据的保留原值并计数。

    研究脚本一次性访问 _by_date 内部结构(生产代码不这么做)。
    """
    rebuilt = FundamentalRegistry()
    replaced = kept = 0
    for day, snaps in registry._by_date.items():  # noqa: SLF001
        for snap in snaps:
            per_sym = mv_map.get(snap.symbol)
            mv = per_sym.get(day) if per_sym else None
            if mv is not None:
                rebuilt.add(replace(snap, market_cap=mv))
                replaced += 1
            else:
                rebuilt.add(snap)
                if snap.symbol in mv_map or is_mainboard(snap.symbol):
                    kept += 1
    return rebuilt, replaced, kept


def _ret_mdd(values: list[float]) -> tuple[float, float]:
    if len(values) < 2:
        return 0.0, 0.0
    ret = values[-1] / values[0] - 1.0
    peak, mdd = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1.0)
    return ret, mdd


def _ew_mainboard_curve(con, start: str, end: str) -> tuple[list[str], list[float]]:
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

    mv_map = _load_totalmv_map(start, end)
    registry, replaced, kept = _override_registry(registry, mv_map)
    print(f"全市场 {len(universe)} → 只主板 {len(mb_universe)} 只 | {start}..{end} | "
          f"split {SPLIT} | top_n={TOP_N} | 指数 {idx}")
    print(f"市值覆写: 替换 {replaced:,} 快照 | 主板未覆写(保留原值) {kept:,} "
          f"({100 * kept / max(replaced + kept, 1):.2f}%)")

    # sanity: 窗口末日按新口径的最小 top10(应与 tushare 总市值口径池一致)
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    day = max(d for d in registry._by_date if d <= end_dt)  # noqa: SLF001
    pool = sorted(
        (sn for sn in registry.get_all_at_date(day)
         if is_mainboard(sn.symbol) and sn.market_cap > 0),
        key=lambda sn: sn.market_cap)[:10]
    print(f"sanity {day.date()} 新口径最小10: "
          + ", ".join(f"{sn.symbol}:{sn.market_cap / 1e8:.1f}亿" for sn in pool))

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

    is_off, oos_off = run(start, SPLIT), run(SPLIT, end)
    mkt.load_bars(fetcher.fetch_history_bars(idx, tf, start, end))
    is_on, oos_on = run(start, SPLIT), run(SPLIT, end)
    full_on = run(start, end)
    fetcher.close()

    con = duckdb.connect(DB, read_only=True)
    bd, bv = _ew_mainboard_curve(con, start, end)
    con.close()
    b_oos = _ret_mdd(_slice(bd, bv, SPLIT, end))

    print("\n=== 总市值口径 · 主板域 F01+趋势闸 四格 ===")
    show("IS  OFF", is_off)
    show("IS  ON ", is_on)
    show("OOS OFF", oos_off)
    show("OOS ON ", oos_on)
    show("全窗 ON", full_on)
    print("\n=== 趋势闸净效应 (ON − OFF) ===")
    print(f"  OOS: 收益 {oos_on.total_return - oos_off.total_return:+.2%} | "
          f"回撤 {oos_on.max_drawdown - oos_off.max_drawdown:+.2%} | "
          f"Sharpe {oos_on.sharpe_ratio - oos_off.sharpe_ratio:+.2f}")

    crit1 = oos_on.max_drawdown < abs(b_oos[1])
    crit2 = (oos_on.sharpe_ratio > oos_off.sharpe_ratio) and (oos_on.max_drawdown < oos_off.max_drawdown)
    v1, v2 = ("✅" if crit1 else "❌"), ("✅" if crit2 else "❌")
    verdict = "PASS" if crit1 and crit2 else "FAIL"
    print("\n=== gate 判据 (DD-4, 总市值口径) ===")
    print(f"  ① OOS 回撤幅度优于只主板等权基准: {oos_on.max_drawdown:.2%} vs {abs(b_oos[1]):.2%} → {v1}")
    print(f"  ② 趋势闸 OOS 增益不蒸发: → {v2}")
    print(f"  裁定: {verdict}")


if __name__ == "__main__":
    main()
