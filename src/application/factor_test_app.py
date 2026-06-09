"""因子测试应用服务 — 数据准备 + 批量测试 + 判决。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.factor_test.factor_catalog import FactorHypothesis
from src.domain.strategy.factor_test.report import ScoredFactorTestReport
from src.domain.strategy.factor_test.verdict import FactorVerdict, judge_factor
from src.domain.strategy.services.cross_section_builder import CrossSectionBuilder
from src.infrastructure.factor_test.test_runner import FactorTestRunner
from src.infrastructure.mock.mock_market import MockMarketGateway

if TYPE_CHECKING:
    from src.domain.market.interfaces.gateways.fundamental_fetcher import IFundamentalFetcher
    from src.domain.market.interfaces.gateways.history_fetcher import IHistoryDataFetcher


@dataclass(slots=True, kw_only=True)
class FactorTestResult:
    """单因子测试结果(含 IS/OOS 判决)。"""
    hypothesis: FactorHypothesis
    is_report: ScoredFactorTestReport
    oos_report: ScoredFactorTestReport | None = None
    verdict: FactorVerdict


class FactorTestAppService:
    """因子测试应用服务。

    职责:
    1. 加载历史数据 → 构建 snapshots_by_date
    2. 批量运行因子测试
    3. 样本内外切分
    4. 硬门槛判决
    """

    def __init__(
        self,
        history_fetcher: IHistoryDataFetcher,
        fundamental_fetcher: IFundamentalFetcher,
    ) -> None:
        self._history_fetcher = history_fetcher
        self._fundamental_fetcher = fundamental_fetcher
        self._runner = FactorTestRunner()

    def prepare_snapshots(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
    ) -> tuple[
        dict[str, list[StockSnapshot]],
        dict[str, dict[str, float]],
        dict[str, dict[str, float]],
    ]:
        """构建因子测试所需的数据结构。

        Returns:
            snapshots_by_date: {date_str: [StockSnapshot, ...]}
            returns_by_date: {date_str: {symbol: next_day_return}}
            prices_by_date: {date_str: {symbol: close_price}}
        """
        market = MockMarketGateway()
        tf = Timeframe.DAY_1

        # 1. 加载行情数据
        for symbol in symbols:
            bars = self._history_fetcher.fetch_history_bars(symbol, tf, start_date, end_date)
            market.load_bars(bars)

        # 2. 加载基本面数据
        registry = FundamentalRegistry()
        fund_snapshots = self._fundamental_fetcher.fetch_by_range(start_date, end_date)
        registry.load_snapshots(fund_snapshots)

        # 3. 按日构建 StockSnapshot
        all_timestamps = market.get_all_timestamps(tf)
        dt_start = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(end_date, "%Y-%m-%d")
        valid_timestamps = [ts for ts in all_timestamps if dt_start <= ts <= dt_end]

        snapshots_by_date: dict[str, list[StockSnapshot]] = {}
        prices_by_date: dict[str, dict[str, float]] = {}

        for ts in valid_timestamps:
            market.set_current_time(ts)
            date_str = ts.strftime("%Y-%m-%d")

            # 获取当日 bar + 历史 bar
            bars_today: dict[str, StockSnapshot] = {}
            bar_history: dict[str, list] = {}
            close_prices: dict[str, float] = {}

            for sym in symbols:
                recent = market.get_recent_bars(sym, tf, 120)
                if len(recent) < 2:
                    continue
                # info_bars = T-1 and earlier (no lookahead)
                info_bars = recent[:-1]
                exec_bar = recent[-1]
                if info_bars:
                    bars_today[sym] = info_bars[-1]
                    bar_history[sym] = info_bars
                    close_prices[sym] = exec_bar.close

            if not bars_today:
                continue

            # CrossSectionBuilder 需要 {symbol: Bar} (当日 bar for snapshot)
            day_bars = {sym: bar for sym, bar in bars_today.items()}
            snapshots = CrossSectionBuilder.build_cross_section(
                ts, day_bars, registry, bar_history
            )
            if snapshots:
                snapshots_by_date[date_str] = snapshots
                prices_by_date[date_str] = close_prices

        # 4. 计算次日收益 (returns_by_date)
        sorted_dates = sorted(snapshots_by_date.keys())
        returns_by_date: dict[str, dict[str, float]] = {}
        for i, date_str in enumerate(sorted_dates):
            if i + 1 >= len(sorted_dates):
                break
            next_date = sorted_dates[i + 1]
            today_prices = prices_by_date.get(date_str, {})
            next_prices = prices_by_date.get(next_date, {})
            day_returns: dict[str, float] = {}
            for sym in today_prices:
                if sym in next_prices and today_prices[sym] > 0:
                    day_returns[sym] = (next_prices[sym] - today_prices[sym]) / today_prices[sym]
            returns_by_date[date_str] = day_returns

        return snapshots_by_date, returns_by_date, prices_by_date

    def run_single(
        self,
        hypothesis: FactorHypothesis,
        snapshots_by_date: dict[str, list[StockSnapshot]],
        returns_by_date: dict[str, dict[str, float]],
        prices_by_date: dict[str, dict[str, float]],
        test_period: tuple[str, str],
        num_layers: int = 5,
    ) -> ScoredFactorTestReport:
        """测试单个因子假设。"""
        return self._runner.run(
            expression_str=hypothesis.expression,
            snapshots_by_date=snapshots_by_date,
            returns_by_date=returns_by_date,
            prices_by_date=prices_by_date,
            test_period=test_period,
            num_layers=num_layers,
        )

    def run_batch(
        self,
        hypotheses: list[FactorHypothesis],
        snapshots_by_date: dict[str, list[StockSnapshot]],
        returns_by_date: dict[str, dict[str, float]],
        prices_by_date: dict[str, dict[str, float]],
        test_period: tuple[str, str],
        split_date: str | None = None,
        num_layers: int = 5,
    ) -> list[FactorTestResult]:
        """批量测试因子假设，支持样本内外切分。

        Args:
            hypotheses: 因子假设列表。
            snapshots_by_date: 全量截面数据。
            returns_by_date: 全量收益数据。
            prices_by_date: 全量价格数据。
            test_period: (start_date, end_date)。
            split_date: 样本内截止日期 (如 "2023-12-31")，None=不做切分。
            num_layers: 分层数。

        Returns:
            list[FactorTestResult]: 每个因子的测试结果+判决。
        """
        results: list[FactorTestResult] = []

        for hyp in hypotheses:
            print(f"  Testing {hyp.factor_id} {hyp.name}: {hyp.expression}")

            # In-sample
            if split_date:
                is_snapshots = {d: v for d, v in snapshots_by_date.items() if d <= split_date}
                is_returns = {d: v for d, v in returns_by_date.items() if d <= split_date}
                is_prices = {d: v for d, v in prices_by_date.items() if d <= split_date}
                is_period = (test_period[0], split_date)
            else:
                is_snapshots = snapshots_by_date
                is_returns = returns_by_date
                is_prices = prices_by_date
                is_period = test_period

            is_report = self.run_single(
                hyp, is_snapshots, is_returns, is_prices, is_period, num_layers
            )

            # Out-of-sample (if split)
            oos_report: ScoredFactorTestReport | None = None
            if split_date:
                oos_snapshots = {d: v for d, v in snapshots_by_date.items() if d > split_date}
                oos_returns = {d: v for d, v in returns_by_date.items() if d > split_date}
                oos_prices = {d: v for d, v in prices_by_date.items() if d > split_date}
                oos_period = (split_date, test_period[1])
                if oos_snapshots:
                    oos_report = self.run_single(
                        hyp, oos_snapshots, oos_returns, oos_prices, oos_period, num_layers
                    )

            verdict = judge_factor(
                is_report, oos_report=oos_report,
                factor_id=hyp.factor_id, factor_name=hyp.name,
            )

            results.append(FactorTestResult(
                hypothesis=hyp,
                is_report=is_report,
                oos_report=oos_report,
                verdict=verdict,
            ))

            status = "PASS" if verdict.passed else "FAIL"
            print(f"    -> {status} | IC={is_report.ic_mean:.4f} IR={is_report.ir:.3f} "
                  f"Score={is_report.score:.0f}({is_report.grade})")

        return results
