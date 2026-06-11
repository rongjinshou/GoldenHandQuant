"""Tests for FactorTestAppService -- mock-based integration test."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.application.factor_test_app import (
    FactorTestAppService,
    FactorTestResult,
    _compute_forward_returns,
)
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.factor_test.factor_catalog import P0_FACTORS
from src.domain.strategy.factor_test.report import FactorTestReport, ScoredFactorTestReport


class _StubHistoryFetcher:
    """真实数据结构的历史行情 stub (非 MagicMock)。"""

    def __init__(self, bars_by_symbol: dict[str, list[Bar]]) -> None:
        self._bars = bars_by_symbol

    def fetch_history_bars(self, symbol, timeframe, start_date, end_date):
        s = datetime.strptime(start_date, "%Y-%m-%d")
        e = datetime.strptime(end_date, "%Y-%m-%d")
        return [b for b in self._bars.get(symbol, []) if s <= b.timestamp <= e]


class _StubFundamentalFetcher:
    """真实数据结构的基本面 stub (非 MagicMock)。"""

    def __init__(self, snapshots: list[FundamentalSnapshot]) -> None:
        self._snapshots = snapshots

    def fetch_by_range(self, start_date, end_date):
        return [
            s for s in self._snapshots
            if start_date <= s.date.strftime("%Y-%m-%d") <= end_date
        ]


def _consecutive_dates(first: str, n: int) -> list[str]:
    """从 first 起连续 n 个自然日 (MockMarketGateway 不区分交易日/自然日)。"""
    d0 = datetime.strptime(first, "%Y-%m-%d")
    return [(d0 + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]


def _make_daily_bars(symbol: str, closes: dict[str, float]) -> list[Bar]:
    """每个日期一根日线 bar, OHLC 同价、量恒定 — close 唯一可辨识来源日。"""
    return [
        Bar(
            symbol=symbol,
            timeframe=Timeframe.DAY_1,
            timestamp=datetime.strptime(d, "%Y-%m-%d"),
            open=c, high=c, low=c, close=c,
            volume=1_000_000.0,
        )
        for d, c in closes.items()
    ]


def _make_fundamentals(symbol: str, dates: list[str]) -> list[FundamentalSnapshot]:
    """每个交易日一条基本面快照 (registry 按 ann_date 精确匹配当日)。"""
    return [
        FundamentalSnapshot(
            symbol=symbol,
            date=datetime.strptime(d, "%Y-%m-%d"),
            name="测试股",
            list_date=datetime(2010, 1, 1),
            market_cap=5_000_000_000.0,
        )
        for d in dates
    ]


def _build_service(
    closes: dict[str, float], symbol: str = "000001.SZ"
) -> FactorTestAppService:
    """用真实数据结构的 stub 组装服务 (走完整 prepare_snapshots 管道)。"""
    return FactorTestAppService(
        history_fetcher=_StubHistoryFetcher({symbol: _make_daily_bars(symbol, closes)}),
        fundamental_fetcher=_StubFundamentalFetcher(
            _make_fundamentals(symbol, list(closes.keys()))
        ),
    )


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

    def test_first_window_day_has_history_features(self):
        """warmup 约定: 窗口首日的 return_5d / volatility_20d 已可算。

        取数从 start-200 天开始, 窗口开头不该有特征 NaN 冷启动期。
        """
        # 40 天 warmup + 5 天窗口, close 线性递增保证特征非平凡
        dates = _consecutive_dates("2024-01-01", 45)
        closes = {d: 10.0 + i * 0.1 for i, d in enumerate(dates)}
        service = _build_service(closes)

        snaps, _, _ = service.prepare_snapshots(
            ["000001.SZ"], "2024-02-10", "2024-02-14"
        )

        first_day = min(snaps.keys())
        assert first_day == "2024-02-10"
        snap = snaps[first_day][0]
        assert snap.return_5d is not None
        assert snap.volatility_20d is not None

    def test_output_window_excludes_warmup_dates(self):
        """warmup 约定: 提前取的数只喂特征, 不进输出 — 键严格落在 [start, end]。"""
        dates = _consecutive_dates("2024-01-01", 45)
        closes = {d: 10.0 + i * 0.1 for i, d in enumerate(dates)}
        service = _build_service(closes)

        snaps, rets, prices = service.prepare_snapshots(
            ["000001.SZ"], "2024-02-10", "2024-02-14"
        )

        for keys in (snaps.keys(), rets.keys(), prices.keys()):
            assert all("2024-02-10" <= d <= "2024-02-14" for d in keys)


class TestPrepareSnapshotsNoLookahead:
    def test_snapshot_features_come_from_t_minus_1_bar(self):
        """T-1 信息约定: T 日快照的价量特征来自 T-1 bar, 执行价才是 T 日 close。

        信号在 T 日开盘前只能依据 T-1 及更早的信息; T 日 close 仅作成交价。
        """
        dates = _consecutive_dates("2024-01-01", 10)
        closes = {d: 10.0 + i for i, d in enumerate(dates)}  # 每日 close 唯一
        service = _build_service(closes)

        snaps, _, prices = service.prepare_snapshots(
            ["000001.SZ"], "2024-01-05", "2024-01-10"
        )

        snap = snaps["2024-01-05"][0]
        # 特征 bar = T-1 (2024-01-04) 的 close, 而非 T 日的
        assert snap.close == closes["2024-01-04"]
        assert snap.close != closes["2024-01-05"]
        # 执行价 = T 日 close
        assert prices["2024-01-05"]["000001.SZ"] == closes["2024-01-05"]

    def test_technical_features_use_info_up_to_t_minus_1(self):
        """无前视约定: return_5d 等窗口特征严格用 T-1 及更早的 close 计算。"""
        dates = _consecutive_dates("2024-01-01", 10)
        closes = {d: 10.0 + i for i, d in enumerate(dates)}
        service = _build_service(closes)

        snaps, _, _ = service.prepare_snapshots(
            ["000001.SZ"], "2024-01-10", "2024-01-10"
        )

        snap = snaps["2024-01-10"][0]
        # info 截止 T-1=01-09: return_5d = (close[01-09] - close[01-04]) / close[01-04]
        expected = (closes["2024-01-09"] - closes["2024-01-04"]) / closes["2024-01-04"]
        assert abs(snap.return_5d - expected) < 1e-12

    def test_future_prices_do_not_affect_past_snapshots(self):
        """无前视约定: 篡改未来 (末日暴涨 10 倍) 不得改变此前任何一天的快照与收益。"""
        dates = _consecutive_dates("2024-01-01", 30)
        closes = {d: 10.0 + i * 0.1 for i, d in enumerate(dates)}
        spiked = dict(closes)
        spiked[dates[-1]] = closes[dates[-1]] * 10  # 只动最后一天

        snaps_a, rets_a, _ = _build_service(closes).prepare_snapshots(
            ["000001.SZ"], "2024-01-20", "2024-01-30"
        )
        snaps_b, rets_b, _ = _build_service(spiked).prepare_snapshots(
            ["000001.SZ"], "2024-01-20", "2024-01-30"
        )

        last_day = dates[-1]
        for d in snaps_a:
            if d == last_day:
                continue
            a, b = snaps_a[d][0], snaps_b[d][0]
            assert a.close == b.close
            assert a.return_5d == b.return_5d
            assert a.volatility_20d == b.volatility_20d
        for d in rets_a:
            if d == last_day:
                continue
            assert rets_a[d] == rets_b[d]

    def test_returns_realized_from_execution_closes(self):
        """收益对齐约定: returns[T] = T-1→T 的执行价收益 (按实现日键入)。"""
        dates = _consecutive_dates("2024-01-01", 10)
        closes = {d: 10.0 + i for i, d in enumerate(dates)}
        service = _build_service(closes)

        _, rets, _ = service.prepare_snapshots(
            ["000001.SZ"], "2024-01-05", "2024-01-10"
        )

        expected = (closes["2024-01-06"] - closes["2024-01-05"]) / closes["2024-01-05"]
        assert abs(rets["2024-01-06"]["000001.SZ"] - expected) < 1e-12


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

    def test_run_batch_passes_objective_and_cost_rate(self):
        """run_batch 应把 objective/cost_rate 透传给 runner 与 judge_factor。"""
        mock_hist = MagicMock()
        mock_fund = MagicMock()
        service = FactorTestAppService(history_fetcher=mock_hist, fundamental_fetcher=mock_fund)
        mock_r = FactorTestReport(
            expression="0 - log(market_cap)",
            test_period=("2023-01-01", "2024-01-01"),
            universe_count=50, ic_mean=0.03, ic_std=0.3, ir=0.1,
            ic_positive_rate=0.55, monotonicity_score=0.8,
            long_short_return=0.0, top_excess_return=0.06, excess_ir=0.7,
            excess_positive_rate=0.6,
        )
        mock_scored = ScoredFactorTestReport(
            report=mock_r, score=60.0, grade="C", grade_reasons=["t"]
        )
        service._runner = MagicMock()
        service._runner.run.return_value = mock_scored

        results = service.run_batch(
            hypotheses=P0_FACTORS[:1],
            snapshots_by_date={"2023-06-01": []},
            returns_by_date={"2023-06-01": {}},
            prices_by_date={"2023-06-01": {}},
            test_period=("2023-01-01", "2024-01-01"),
            objective="long_only", cost_rate=0.005,
        )
        assert service._runner.run.call_args.kwargs["objective"] == "long_only"
        assert service._runner.run.call_args.kwargs["cost_rate"] == 0.005
        assert results[0].verdict.objective == "long_only"
        assert results[0].verdict.top_excess_return == 0.06

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
