from datetime import datetime, timedelta

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.risk.services.portfolio.stress_scenarios.historical_scenarios import (
    StressScenario,
)
from src.domain.risk.services.portfolio.stress_test_runner import StressTestRunner
from src.domain.risk.value_objects.correlation_matrix import CorrelationMatrix


def _make_report(
    name: str,
    dates: list[datetime],
    daily_returns: list[float],
    final_capital: float = 100000.0,
) -> BacktestReport:
    return BacktestReport(
        start_date=dates[0] if dates else datetime(2020, 1, 1),
        end_date=dates[-1] if dates else datetime(2020, 12, 31),
        initial_capital=100000.0,
        final_capital=final_capital,
        total_return=0.0,
        annualized_return=0.0,
        max_drawdown=0.1,
        win_rate=0.5,
        profit_loss_ratio=1.0,
        trade_count=0,
        dates=dates,
        daily_returns=daily_returns,
        strategy_name=name,
    )


def _dates(start: datetime, n: int) -> list[datetime]:
    return [start + timedelta(days=i) for i in range(n)]


def _make_correlation(names: list[str], corr: float = 0.0) -> CorrelationMatrix:
    n = len(names)
    matrix = [[1.0 if i == j else corr for j in range(n)] for i in range(n)]
    return CorrelationMatrix(strategy_names=names, matrix=matrix)


class TestStressTestRunner:
    def test_historical_scenario_extracts_returns(self):
        dates = _dates(datetime(2015, 6, 1), 30)
        returns = [-0.03] * 30
        report = _make_report("A", dates, returns)
        runner = StressTestRunner()
        results = runner.run_historical({"A": report}, {"A": 1.0})
        assert len(results) == 4
        # 2015 scenario should have data
        r2015 = next(r for r in results if "2015" in r.scenario_name)
        assert r2015.portfolio_loss < 0

    def test_historical_pass_fail(self):
        dates = _dates(datetime(2015, 6, 1), 30)
        returns = [-0.01] * 30
        report = _make_report("A", dates, returns)
        runner = StressTestRunner(loss_threshold=0.15)
        results = runner.run_historical({"A": report}, {"A": 1.0})
        r2015 = next(r for r in results if "2015" in r.scenario_name)
        # (0.99)^30 ≈ 0.74, loss ≈ 26% > 15% threshold -> fail
        assert r2015.passed is False

    def test_hypothetical_market_crash(self):
        dates = _dates(datetime(2020, 1, 1), 30)
        returns = [0.005] * 30
        report = _make_report("A", dates, returns)
        runner = StressTestRunner()
        corr = _make_correlation(["A"])
        results = runner.run_hypothetical({"A": report}, {"A": 1.0}, corr)
        assert len(results) == 5
        crash = next(r for r in results if r.scenario_name == "市场暴跌")
        assert crash.portfolio_loss < 0

    def test_hypothetical_correlation_crisis(self):
        dates = _dates(datetime(2020, 1, 1), 30)
        a = _make_report("A", dates, [0.01] * 30)
        b = _make_report("B", dates, [0.01] * 30)
        runner = StressTestRunner()
        corr = _make_correlation(["A", "B"])
        results = runner.run_hypothetical(
            {"A": a, "B": b}, {"A": 0.5, "B": 0.5}, corr
        )
        crisis = next(r for r in results if r.scenario_name == "相关性崩溃")
        assert crisis.portfolio_loss < 0

    def test_run_all(self):
        dates = _dates(datetime(2020, 1, 1), 30)
        returns = [0.01] * 30
        report = _make_report("A", dates, returns)
        runner = StressTestRunner()
        corr = _make_correlation(["A"])
        results = runner.run_all({"A": report}, {"A": 1.0}, corr)
        assert len(results) == 9  # 4 historical + 5 hypothetical

    def test_custom_scenarios(self):
        runner = StressTestRunner(
            historical_scenarios=[],
            hypothetical_scenarios=[
                StressScenario(
                    name="Custom",
                    scenario_type="hypothetical",
                    description="test",
                    shock_params={"shock_factor": -0.05},
                )
            ],
        )
        dates = _dates(datetime(2020, 1, 1), 10)
        report = _make_report("A", dates, [0.01] * 10)
        corr = _make_correlation(["A"])
        results = runner.run_all({"A": report}, {"A": 1.0}, corr)
        assert len(results) == 1
        assert results[0].scenario_name == "Custom"
