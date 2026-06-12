"""BacktestReport → backtest_runs 行映射（持久化口径单一来源）。

设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md DD-5
"""

from __future__ import annotations

import json

from src.domain.backtest.entities.backtest_report import BacktestReport

# 单行 JSON 防失控: 日频策略全年也就数百笔, 2000 已远超正常范围
_TRADES_CAP = 2000


def build_backtest_run_row(report: BacktestReport, *, run_id: str,
                           params: dict) -> dict:
    curve = {
        "dates": [d.strftime("%Y-%m-%d") for d in report.dates],
        "values": list(report.equity_curve),
    }
    trades = [
        {"date": t.execute_at.strftime("%Y-%m-%d"), "symbol": t.symbol,
         "direction": t.direction.value, "price": t.price, "volume": t.volume,
         "pnl": t.realized_pnl}
        for t in (report.trades or [])[:_TRADES_CAP]
    ]
    return {
        "run_id": run_id,
        "strategy": report.strategy_name or "unknown",
        "start_date": report.start_date.strftime("%Y-%m-%d"),
        "end_date": report.end_date.strftime("%Y-%m-%d"),
        "initial_capital": report.initial_capital,
        "params": json.dumps(params, ensure_ascii=False),
        "total_return": report.total_return,
        "annualized_return": report.annualized_return,
        "max_drawdown": report.max_drawdown,
        "sharpe_ratio": report.sharpe_ratio,
        "sortino_ratio": report.sortino_ratio,
        "calmar_ratio": report.calmar_ratio,
        "win_rate": report.win_rate,
        "trade_count": report.trade_count,
        "turnover_rate": report.turnover_rate,
        "equity_curve": json.dumps(curve),
        "trades": json.dumps(trades, ensure_ascii=False),
    }
