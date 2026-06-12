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

    def test_read_only_old_schema_db_returns_empty(self, tmp_path):
        """旧库(无 backtest_runs 表)被 read_only 打开时优雅返回空, 不 500。"""
        import duckdb

        db = str(tmp_path / "old.duckdb")
        duckdb.connect(db).close()  # 建一个不含任何表的旧库

        store = MarketDataStore(db, read_only=True)
        try:
            assert store.load_backtest_runs() == []
        finally:
            store.close()

    def test_reinsert_same_key_is_idempotent(self):
        store = MarketDataStore(":memory:")
        row = build_backtest_run_row(_report(), run_id="r1", params={})
        store.insert_backtest_runs([row])
        store.insert_backtest_runs([dict(row, total_return=0.2)])

        runs = store.load_backtest_runs()

        assert len(runs) == 1
        assert runs[0]["strategies"][0]["total_return"] == 0.2

class TestTradesColumn:
    """v3 回测可视: 买卖事件随 run 入库 (基准/标记可视化的数据底座)。"""

    def _report_with_trades(self) -> BacktestReport:
        from dataclasses import replace

        from src.domain.backtest.value_objects.trade_record import TradeRecord
        from src.domain.trade.value_objects.order_direction import OrderDirection
        return replace(_report(), trades=[
            TradeRecord(symbol="000021.SZ", direction=OrderDirection.BUY,
                        execute_at=datetime(2024, 1, 2), price=10.5, volume=100),
            TradeRecord(symbol="000021.SZ", direction=OrderDirection.SELL,
                        execute_at=datetime(2024, 1, 3), price=11.2, volume=100,
                        realized_pnl=63.5),
        ])

    def test_row_serializes_trades(self):
        row = build_backtest_run_row(self._report_with_trades(), run_id="r1", params={})

        trades = json.loads(row["trades"])
        assert trades == [
            {"date": "2024-01-02", "symbol": "000021.SZ", "direction": "BUY",
             "price": 10.5, "volume": 100, "pnl": 0.0},
            {"date": "2024-01-03", "symbol": "000021.SZ", "direction": "SELL",
             "price": 11.2, "volume": 100, "pnl": 63.5},
        ]

    def test_store_roundtrip_keeps_trades(self):
        store = MarketDataStore(":memory:")
        row = build_backtest_run_row(self._report_with_trades(), run_id="r1", params={})
        store.insert_backtest_runs([row])

        s = store.load_backtest_runs()[0]["strategies"][0]
        assert json.loads(s["trades"])[1]["pnl"] == 63.5

    def test_migration_adds_trades_to_legacy_table(self, tmp_path):
        """存量库无 trades 列 → 写模式打开自动迁移, 旧行读出 None。"""
        import duckdb
        path = str(tmp_path / "legacy.duckdb")
        conn = duckdb.connect(path)
        conn.execute("""CREATE TABLE backtest_runs (
            run_id VARCHAR NOT NULL, created_at TIMESTAMP NOT NULL,
            strategy VARCHAR NOT NULL,
            start_date DATE, end_date DATE, initial_capital DOUBLE,
            params VARCHAR,
            total_return DOUBLE, annualized_return DOUBLE, max_drawdown DOUBLE,
            sharpe_ratio DOUBLE, sortino_ratio DOUBLE, calmar_ratio DOUBLE,
            win_rate DOUBLE, trade_count INTEGER, turnover_rate DOUBLE,
            equity_curve VARCHAR,
            PRIMARY KEY (run_id, strategy))""")
        conn.execute("""INSERT INTO backtest_runs VALUES
            ('old', '2026-06-12 09:00:00', 'dual_ma', '2024-01-01', '2024-03-31',
             1e6, '{}', 0.1, 0.1, 0.05, 1.0, 1.0, 1.0, 0.5, 4, 0.01, '{}')""")
        conn.close()

        store = MarketDataStore(path)
        s = store.load_backtest_runs()[0]["strategies"][0]
        store.close()
        assert s["trades"] is None  # 旧行无留痕, API 层转 []

    def test_trades_capped_at_limit(self):
        """超长交易列表截断, 防单行 JSON 失控。"""
        from dataclasses import replace

        from src.domain.backtest.value_objects.trade_record import TradeRecord
        from src.domain.trade.value_objects.order_direction import OrderDirection
        r = replace(_report(), trades=[
            TradeRecord(symbol="A", direction=OrderDirection.BUY,
                        execute_at=datetime(2024, 1, 2), price=1.0, volume=100)
        ] * 2500)

        row = build_backtest_run_row(r, run_id="r1", params={})

        assert len(json.loads(row["trades"])) == 2000

    def test_read_only_legacy_table_without_trades_column(self, tmp_path):
        """read_only 打开缺 trades 列的旧库: 正常读出, trades=None, 不许 500。"""
        import duckdb
        path = str(tmp_path / "legacy_ro.duckdb")
        conn = duckdb.connect(path)
        conn.execute("""CREATE TABLE backtest_runs (
            run_id VARCHAR NOT NULL, created_at TIMESTAMP NOT NULL,
            strategy VARCHAR NOT NULL,
            start_date DATE, end_date DATE, initial_capital DOUBLE,
            params VARCHAR,
            total_return DOUBLE, annualized_return DOUBLE, max_drawdown DOUBLE,
            sharpe_ratio DOUBLE, sortino_ratio DOUBLE, calmar_ratio DOUBLE,
            win_rate DOUBLE, trade_count INTEGER, turnover_rate DOUBLE,
            equity_curve VARCHAR,
            PRIMARY KEY (run_id, strategy))""")
        conn.execute("""INSERT INTO backtest_runs VALUES
            ('old', '2026-06-12 09:00:00', 'dual_ma', '2024-01-01', '2024-03-31',
             1e6, '{}', 0.1, 0.1, 0.05, 1.0, 1.0, 1.0, 0.5, 4, 0.01, '{}')""")
        conn.close()

        ro = MarketDataStore(path, read_only=True)
        runs = ro.load_backtest_runs()
        ro.close()

        assert runs[0]["strategies"][0]["total_return"] == 0.1
        assert runs[0]["strategies"][0]["trades"] is None
