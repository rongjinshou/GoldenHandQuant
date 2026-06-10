"""Tests for FactorTestAppService -- mock-based integration test."""

from unittest.mock import MagicMock

from src.application.factor_test_app import (
    FactorTestAppService,
    FactorTestResult,
    _compute_forward_returns,
)
from src.domain.strategy.factor_test.factor_catalog import P0_FACTORS
from src.domain.strategy.factor_test.report import FactorTestReport, ScoredFactorTestReport


class TestPrepareSnapshotsWarmup:
    def test_loads_warmup_history_before_start(self):
        """取数应提前一段(warmup), 让开头日期的 return_60d 等特征可算。"""
        mock_hist = MagicMock()
        mock_hist.fetch_history_bars.return_value = []
        mock_fund = MagicMock()
        mock_fund.fetch_by_range.return_value = []
        service = FactorTestAppService(history_fetcher=mock_hist, fundamental_fetcher=mock_fund)

        service.prepare_snapshots(["000001.SZ"], "2024-01-01", "2024-06-30")

        # fetch_history_bars(symbol, tf, start, end) — start 应早于请求的 2024-01-01
        call_start = mock_hist.fetch_history_bars.call_args[0][2]
        assert call_start < "2024-01-01"


class TestForwardReturnsAlignment:
    def test_returns_keyed_by_realized_date(self):
        """收益须按【实现日(end date)】键入，与 ICCalculator 的 next_date 约定对齐。

        防 off-by-one: factor@prev 经引擎 next_date 查到 returns[cur],
        预测 prev->cur 的收益。若按 start date 键入则错位一天。
        """
        prices_by_date = {
            "2024-01-02": {"A": 10.0, "B": 100.0},
            "2024-01-03": {"A": 11.0, "B": 90.0},   # A +10%, B -10%
            "2024-01-04": {"A": 11.0, "B": 99.0},   # A 0%, B +10%
        }

        rets = _compute_forward_returns(prices_by_date)

        # 键应是实现日 01-03 / 01-04（首日 01-02 无前一日, 不产出收益）
        assert set(rets.keys()) == {"2024-01-03", "2024-01-04"}
        # 01-03 实现的收益 = 01-02 -> 01-03
        assert abs(rets["2024-01-03"]["A"] - 0.10) < 1e-9
        assert abs(rets["2024-01-03"]["B"] - (-0.10)) < 1e-9
        # 01-04 实现的收益 = 01-03 -> 01-04
        assert abs(rets["2024-01-04"]["A"] - 0.0) < 1e-9
        assert abs(rets["2024-01-04"]["B"] - 0.10) < 1e-9


class TestFactorTestAppServiceRunSingle:
    def test_run_single_calls_runner(self):
        """Verify run_single delegates to FactorTestRunner."""
        mock_hist = MagicMock()
        mock_fund = MagicMock()
        service = FactorTestAppService(
            history_fetcher=mock_hist,
            fundamental_fetcher=mock_fund,
        )
        # Mock the runner
        service._runner = MagicMock()
        mock_report = MagicMock()
        service._runner.run.return_value = mock_report

        result = service.run_single(
            P0_FACTORS[0],
            snapshots_by_date={},
            returns_by_date={},
            prices_by_date={},
            test_period=("2021-01-01", "2025-12-31"),
        )

        service._runner.run.assert_called_once()
        assert result is mock_report


class TestFactorTestAppServiceRunBatch:
    def test_run_batch_with_split(self):
        """Verify batch run creates IS + OOS reports when split_date is set."""
        mock_hist = MagicMock()
        mock_fund = MagicMock()
        service = FactorTestAppService(
            history_fetcher=mock_hist,
            fundamental_fetcher=mock_fund,
        )
        # Mock runner to return a valid report
        mock_r = FactorTestReport(
            expression="0 - return_20d",
            test_period=("2021-01-01", "2025-12-31"),
            universe_count=100,
            ic_mean=0.04, ic_std=0.02, ir=0.5,
            ic_positive_rate=0.6, monotonicity_score=0.8,
            long_short_return=0.1,
        )
        mock_scored = ScoredFactorTestReport(
            report=mock_r, score=75.0, grade="B", grade_reasons=["test"]
        )
        service._runner = MagicMock()
        service._runner.run.return_value = mock_scored

        # Fake data with two dates
        snapshots = {"2023-01-01": [], "2024-01-01": []}
        returns = {"2023-01-01": {}, "2024-01-01": {}}
        prices = {"2023-01-01": {}, "2024-01-01": {}}

        results = service.run_batch(
            hypotheses=P0_FACTORS[:1],
            snapshots_by_date=snapshots,
            returns_by_date=returns,
            prices_by_date=prices,
            test_period=("2023-01-01", "2024-01-01"),
            split_date="2023-12-31",
        )

        assert len(results) == 1
        assert isinstance(results[0], FactorTestResult)
        # Runner called twice (IS + OOS)
        assert service._runner.run.call_count == 2

    def test_run_batch_passes_rebalance_days_to_runner(self):
        """run_batch 应把 rebalance_days 透传给 FactorTestRunner。"""
        mock_hist = MagicMock()
        mock_fund = MagicMock()
        service = FactorTestAppService(
            history_fetcher=mock_hist,
            fundamental_fetcher=mock_fund,
        )
        mock_r = FactorTestReport(
            expression="0 - return_20d",
            test_period=("2023-01-01", "2024-01-01"),
            universe_count=50,
            ic_mean=0.03, ic_std=0.015, ir=0.4,
            ic_positive_rate=0.55, monotonicity_score=0.6,
            long_short_return=0.05,
        )
        mock_scored = ScoredFactorTestReport(
            report=mock_r, score=60.0, grade="C", grade_reasons=["test"]
        )
        service._runner = MagicMock()
        service._runner.run.return_value = mock_scored

        service.run_batch(
            hypotheses=P0_FACTORS[:1],
            snapshots_by_date={"2023-06-01": []},
            returns_by_date={"2023-06-01": {}},
            prices_by_date={"2023-06-01": {}},
            test_period=("2023-01-01", "2024-01-01"),
            rebalance_days=5,
        )

        assert service._runner.run.call_args.kwargs["rebalance_days"] == 5

    def test_run_batch_without_split(self):
        """Verify batch run creates only IS report when no split_date."""
        mock_hist = MagicMock()
        mock_fund = MagicMock()
        service = FactorTestAppService(
            history_fetcher=mock_hist,
            fundamental_fetcher=mock_fund,
        )
        mock_r = FactorTestReport(
            expression="0 - return_20d",
            test_period=("2023-01-01", "2024-01-01"),
            universe_count=50,
            ic_mean=0.03, ic_std=0.015, ir=0.4,
            ic_positive_rate=0.55, monotonicity_score=0.6,
            long_short_return=0.05,
        )
        mock_scored = ScoredFactorTestReport(
            report=mock_r, score=60.0, grade="C", grade_reasons=["test"]
        )
        service._runner = MagicMock()
        service._runner.run.return_value = mock_scored

        snapshots = {"2023-06-01": [], "2023-12-01": []}
        returns = {"2023-06-01": {}, "2023-12-01": {}}
        prices = {"2023-06-01": {}, "2023-12-01": {}}

        results = service.run_batch(
            hypotheses=P0_FACTORS[:2],
            snapshots_by_date=snapshots,
            returns_by_date=returns,
            prices_by_date=prices,
            test_period=("2023-01-01", "2024-01-01"),
            split_date=None,
        )

        assert len(results) == 2
        # Runner called once per hypothesis (no OOS)
        assert service._runner.run.call_count == 2
        # No OOS report
        for r in results:
            assert r.oos_report is None
