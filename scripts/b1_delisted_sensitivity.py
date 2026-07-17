"""B1 敏感性矩阵: 含退市股宇宙下 F01+趋势闸 的画像变化(近似修正, 量化生存者偏差折扣)。

矩阵 = {基线(qmt), 含退市(qmt+akshare)} × {严格ST, 宽松ST} × {闸ON, OFF} × {全窗, OOS}:
- 基线(严格) 4 格: 对照 B2 已知数字(全窗ON 145%/OOS Sharpe 1.73), 兼验退市强平对活股零影响;
- 含退市 严格 4 格: 终名带帽被 ST 闸剔 → 修正量下界;
- 含退市 宽松 4 格: 跳过 ST 闸(runtime patch, 不动 domain) → 修正量上界。
口径: top20 / ¥146k / 2021-01-01→2026-06-11 / split 2024-06-30 / 全市场域(B2 原始语境)。
用法: $WIN_PYTHON scripts/b1_delisted_sensitivity.py   (离线, 只读 market.duckdb; 全程数十分钟)
设计: docs/feat/0704-b1-delisted-backfill/2026-07-04-b1-delisted-backfill-design.md DD-10
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.getcwd())

import src.domain.strategy.services.strategies.micro_value_strategy as _mvs  # noqa: E402
from src.application.backtest_app import BacktestAppService  # noqa: E402
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator  # noqa: E402
from src.domain.market.value_objects.timeframe import Timeframe  # noqa: E402
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer  # noqa: E402
from src.domain.strategy.registry import create_strategy  # noqa: E402
from src.infrastructure.config.settings import load_backtest_config  # noqa: E402
from src.infrastructure.gateway.duckdb_history_data import DuckDBHistoryDataFetcher  # noqa: E402
from src.infrastructure.mock.mock_market import MockMarketGateway  # noqa: E402
from src.infrastructure.mock.mock_trade import MockTradeGateway  # noqa: E402
from src.infrastructure.persistence.status_registry_loader import (  # noqa: E402
    build_status_registry_from_db,
)
from src.interfaces.cli._backtest_wiring import build_backtest_cross_section  # noqa: E402

TOP_N, SPLIT = 20, "2024-06-30"
OUT_MD = "docs/feat/0704-b1-delisted-backfill/2026-07-04-sensitivity-results.md"
_ORIG_FILTER_ST = _mvs.filter_st


def _run(mkt, universe, registry, risk_settings, cap, w_start, w_end):
    status_registry = build_status_registry_from_db(start=w_start, end=w_end)
    trade = MockTradeGateway(market_gateway=mkt, initial_capital=cap,
                             stock_status_registry=status_registry)
    app = BacktestAppService(
        market_gateway=mkt, trade_gateway=trade,
        strategy=create_strategy("micro_value", {"top_n": TOP_N}),
        evaluator=PerformanceEvaluator(), sizer=EqualWeightSizer(n_symbols=TOP_N),
        fundamental_registry=registry, status_registry=status_registry,
        risk_settings=risk_settings)
    report = app.run_backtest(
        universe, start_date=datetime.strptime(w_start, "%Y-%m-%d"),
        end_date=datetime.strptime(w_end, "%Y-%m-%d"), base_timeframe=Timeframe.DAY_1)[0]
    return report, trade


def _delisted_stats(trade_gw, delisted: set[str]) -> dict:
    """退市股在成交流水中的足迹: 入选只数/买入额/已实现损益(卖-买, 含强平)。"""
    buys, sells, syms = 0.0, 0.0, set()
    liq = 0
    for t in trade_gw.list_trade_records():
        if t.symbol not in delisted:
            continue
        syms.add(t.symbol)
        notional = t.price * t.volume
        if t.direction.value == "BUY":
            buys += notional
        else:
            sells += notional
            if getattr(t, "remark", "").startswith("delisted-liquidation"):
                liq += 1
    return {"symbols": len(syms), "buy_notional": round(buys),
            "realized_pnl": round(sells - buys), "forced_liquidations": liq}


def main() -> None:
    s = load_backtest_config("resources/backtest.yaml")
    start, end, cap = s.backtest.start_date, s.backtest.end_date, s.backtest.initial_capital
    idx = s.risk.system_gate.index_symbol
    tf = Timeframe.DAY_1

    reg_base, uni_base = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", start, end, config_symbols=[])
    reg_full, uni_full = build_backtest_cross_section(
        "DuckDBHistoryDataFetcher", start, end, config_symbols=[],
        include_sources=("qmt", "akshare"))
    delisted = sorted(set(uni_full) - set(uni_base))
    print(f"基线宇宙 {len(uni_base)} | 含退市 {len(uni_full)} (+{len(delisted)} 退市股) | "
          f"{start}..{end} split {SPLIT} top{TOP_N}")

    mkt = MockMarketGateway()
    fetcher = DuckDBHistoryDataFetcher(fallback=None)
    for i, sym in enumerate(uni_full, start=1):
        mkt.load_bars(fetcher.fetch_history_bars(sym, tf, start, end))
        if i % 800 == 0:
            print(f"  bars 装载 {i}/{len(uni_full)}")
    index_bars = fetcher.fetch_history_bars(idx, tf, start, end)
    fetcher.close()

    def set_gate(on: bool) -> None:
        if on:
            mkt.add_bars(idx, index_bars) if idx not in mkt.data else None
        else:
            mkt.data.pop(idx, None)

    def set_st(strict: bool) -> None:
        _mvs.filter_st = _ORIG_FILTER_ST if strict else (lambda snaps: snaps)

    grids = [
        ("基线(qmt)·严格ST", uni_base, reg_base, True),
        ("含退市·严格ST", uni_full, reg_full, True),
        ("含退市·宽松ST", uni_full, reg_full, False),
    ]
    results: dict[str, dict] = {}
    for tag, uni, reg, strict in grids:
        set_st(strict)
        for gate_on in (False, True):
            set_gate(gate_on)
            for w_tag, (w0, w1) in (("全窗", (start, end)), ("OOS", (SPLIT, end))):
                key = f"{tag}·闸{'ON' if gate_on else 'OFF'}·{w_tag}"
                print(f"\n>>> {key}")
                report, trade = _run(mkt, uni, reg, s.risk, cap, w0, w1)
                results[key] = {
                    "return": report.total_return, "mdd": report.max_drawdown,
                    "sharpe": report.sharpe_ratio, "trades": report.trade_count,
                    "delisted": _delisted_stats(trade, set(delisted)),
                }
                r = results[key]
                print(f"    收益 {r['return']:+.2%} | 回撤 {r['mdd']:.2%} | Sharpe {r['sharpe']:.2f} | "
                      f"退市足迹 {r['delisted']}")
    set_st(True)

    lines = [
        "# B1 敏感性矩阵结果(自动生成)", "",
        f"宇宙: 基线 {len(uni_base)} / 含退市 {len(uni_full)}(+{len(delisted)}); "
        f"口径 top{TOP_N}/¥{cap:,.0f}/{start}→{end}/split {SPLIT}; 市值≈不复权价×股本(akshare)。", "",
        "| 格 | 收益 | 回撤 | Sharpe | 成交 | 退市股(入选只/买入额/实现盈亏/强平次) |",
        "|---|---|---|---|---|---|",
    ]
    for key, r in results.items():
        d = r["delisted"]
        lines.append(f"| {key} | {r['return']:+.2%} | {r['mdd']:.2%} | {r['sharpe']:.2f} | "
                     f"{r['trades']} | {d['symbols']} / ¥{d['buy_notional']:,} / "
                     f"¥{d['realized_pnl']:,} / {d['forced_liquidations']} |")
    md = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    with open(OUT_MD.replace(".md", ".json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"\n结果已写 {OUT_MD}")


if __name__ == "__main__":
    main()
