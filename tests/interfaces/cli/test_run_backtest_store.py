"""store_backtest_reports 可复现元数据测试（2026-07-10 六西格玛体检 C2）。"""

import json
from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.infrastructure.persistence.market_data_store import MarketDataStore
from src.interfaces.cli.run_backtest import store_backtest_reports


def _report() -> BacktestReport:
    return BacktestReport(
        start_date=datetime(2024, 1, 1), end_date=datetime(2024, 6, 30),
        initial_capital=100000.0, final_capital=110000.0,
        total_return=0.1, annualized_return=0.2, max_drawdown=0.05,
        win_rate=0.6, profit_loss_ratio=1.5, trade_count=10,
        strategy_name="micro_value",
    )


class TestReproducibilityMetadata:
    def test_params_enriched_with_repro_block(self, tmp_path, monkeypatch):
        """confirmed-gap(2026-07-10 六西格玛体检 C2): backtest_runs 无 git_sha/
        数据指纹/特征版本/宇宙口径 —— 同参不同代码或数据版本的两次跑不可区分,
        结论无法审计。入库漏斗统一注入 repro 块。"""
        db = str(tmp_path / "m.duckdb")
        monkeypatch.setenv("GHQ_MARKET_DB", db)
        monkeypatch.delenv("GHQ_NO_STORE", raising=False)

        store_backtest_reports([_report()], params={"source": "unit-test"})

        store = MarketDataStore(db, read_only=True)
        try:
            runs = store.load_backtest_runs()
        finally:
            store.close()
        assert len(runs) == 1
        raw = runs[0]["strategies"][0]["params"]
        params = json.loads(raw) if isinstance(raw, str) else raw
        repro = params["repro"]
        assert repro["feature_version"] >= 1
        assert "git_sha" in repro           # 无 git 环境时为 "unknown", 键必须在
        assert "git_dirty" in repro
        assert "bars_rows" in repro          # 数据指纹: 行数 + 最新日期
        assert "bars_max_date" in repro
        assert params["survivorship"] == "unspecified"  # 调用方没标 → 显式可见
        assert params["source"] == "unit-test"          # 原有 params 不受影响

    def test_caller_survivorship_is_kept(self, tmp_path, monkeypatch):
        db = str(tmp_path / "m.duckdb")
        monkeypatch.setenv("GHQ_MARKET_DB", db)
        monkeypatch.delenv("GHQ_NO_STORE", raising=False)

        store_backtest_reports(
            [_report()], params={"survivorship": "qmt+akshare(含退市)"})

        store = MarketDataStore(db, read_only=True)
        try:
            runs = store.load_backtest_runs()
        finally:
            store.close()
        raw = runs[0]["strategies"][0]["params"]
        params = json.loads(raw) if isinstance(raw, str) else raw
        assert params["survivorship"] == "qmt+akshare(含退市)"
