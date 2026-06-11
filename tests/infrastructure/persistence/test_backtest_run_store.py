"""backtest_runs 入库测试 — mapper 行构造 + DuckDB 读写分组。"""
import json
from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.infrastructure.persistence.backtest_run_mapper import build_backtest_run_row
from src.infrastructure.persistence.market_data_store import MarketDataStore


def _report() -> BacktestReport:
    return BacktestReport(
        start_date=datetime(2024, 1, 1), end_date=datetime(2024, 12, 31),
        initial_capital=100000.0, final_capital=112000.0,
        total_return=0.12, annualized_return=0.12, max_drawdown=0.08,
        win_rate=0.55, profit_loss_ratio=1.6, trade_count=42,
        dates=[datetime(2024, 1, 2), datetime(2024, 1, 3)],
        equity_curve=[100000.0, 100500.0], daily_returns=[0.0, 0.005],
        strategy_name="dual_ma",
    )


class TestBacktestRunMapper:
    def test_row_contains_metrics_and_curve(self):
        row = build_backtest_run_row(_report(), run_id="r1", params={"timeframe": "1d"})

        assert row["run_id"] == "r1" and row["strategy"] == "dual_ma"
        assert row["total_return"] == 0.12 and row["trade_count"] == 42
        assert row["sharpe_ratio"] == _report().sharpe_ratio
        curve = json.loads(row["equity_curve"])
        assert curve["dates"] == ["2024-01-02", "2024-01-03"]
        assert curve["values"] == [100000.0, 100500.0]


class TestBacktestRunStore:
    def test_insert_and_load_grouped_by_run(self):
        store = MarketDataStore(":memory:")
        row = build_backtest_run_row(_report(), run_id="r1", params={})
        store.insert_backtest_runs([row])

        runs = store.load_backtest_runs()

        assert len(runs) == 1
        assert runs[0]["run_id"] == "r1"
        assert runs[0]["strategies"][0]["strategy"] == "dual_ma"
        assert runs[0]["strategies"][0]["total_return"] == 0.12

    def test_same_run_id_two_strategies_grouped(self):
        store = MarketDataStore(":memory:")
        r1 = build_backtest_run_row(_report(), run_id="r1", params={})
        r2 = dict(r1, strategy="micro_value")
        store.insert_backtest_runs([r1, r2])

        runs = store.load_backtest_runs()

        assert len(runs) == 1 and len(runs[0]["strategies"]) == 2

    def test_reinsert_same_key_is_idempotent(self):
        store = MarketDataStore(":memory:")
        row = build_backtest_run_row(_report(), run_id="r1", params={})
        store.insert_backtest_runs([row])
        store.insert_backtest_runs([dict(row, total_return=0.2)])

        runs = store.load_backtest_runs()

        assert len(runs) == 1
        assert runs[0]["strategies"][0]["total_return"] == 0.2
