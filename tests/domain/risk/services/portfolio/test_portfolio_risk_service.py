from datetime import datetime, timedelta

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.risk.services.portfolio.portfolio_risk_service import PortfolioRiskService
from src.domain.risk.value_objects.correlation_matrix import CorrelationMatrix
from src.domain.risk.value_objects.diversification_result import DiversificationResult
from src.domain.risk.value_objects.ml_risk_alert import MLRiskAlert
from src.domain.risk.value_objects.stress_test_result import StressTestResult
from src.domain.risk.value_objects.var_result import VaRResult


def _make_report(name: str, returns: list[float], final_capital: float = 100000.0) -> BacktestReport:
    n = len(returns)
    dates = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(n)]
    return BacktestReport(
        start_date=dates[0],
        end_date=dates[-1],
        initial_capital=100000.0,
        final_capital=final_capital,
        total_return=0.0,
        annualized_return=0.0,
        max_drawdown=0.1,
        win_rate=0.5,
        profit_loss_ratio=1.0,
        trade_count=0,
        dates=dates,
        daily_returns=returns,
        strategy_name=name,
    )


class TestPortfolioRiskService:
    def setup_method(self):
        self.service = PortfolioRiskService()

    def test_generate_report_basic(self):
        returns_a = [0.01 * ((-1) ** i) for i in range(100)]
        returns_b = [0.01 * ((-1) ** (i + 1)) for i in range(100)]
        returns_c = [0.005 for _ in range(100)]
        reports = {
            "A": _make_report("A", returns_a),
            "B": _make_report("B", returns_b),
            "C": _make_report("C", returns_c),
        }
        weights = {"A": 0.4, "B": 0.35, "C": 0.25}
        report = self.service.generate_report(reports, weights)
        assert report.strategy_count == 3
        assert report.overall_risk_level in ("low", "medium", "high", "critical")
        assert report.var_95.confidence_level == 0.95
        assert report.var_99.confidence_level == 0.99
        assert len(report.stress_tests) == 9  # 4 historical + 5 hypothetical

    def test_assess_risk_level_low(self):
        div = DiversificationResult(
            diversification_ratio=1.5, effective_strategies=3.0,
            concentration_index=0.2, max_pairwise_correlation=0.3,
            is_well_diversified=True,
        )
        var_95 = VaRResult(
            confidence_level=0.95, method="historical",
            var_absolute=1000, var_percentage=0.01, cvar=0.015,
            holding_period=1, portfolio_value=100000,
        )
        level = self.service.assess_risk_level(div, var_95, [], [])
        assert level == "low"

    def test_assess_risk_level_critical_stress_fail(self):
        div = DiversificationResult(
            diversification_ratio=1.5, effective_strategies=3.0,
            concentration_index=0.2, max_pairwise_correlation=0.3,
            is_well_diversified=True,
        )
        var_95 = VaRResult(
            confidence_level=0.95, method="historical",
            var_absolute=1000, var_percentage=0.01, cvar=0.015,
            holding_period=1, portfolio_value=100000,
        )
        stress = [StressTestResult(
            scenario_name="test", scenario_type="historical",
            description="", portfolio_loss=-0.2, strategy_losses={},
            max_drawdown_under_stress=0.2, recovery_days=-1, passed=False,
        )]
        level = self.service.assess_risk_level(div, var_95, stress, [])
        assert level == "critical"

    def test_assess_risk_level_high_var(self):
        div = DiversificationResult(
            diversification_ratio=1.5, effective_strategies=3.0,
            concentration_index=0.2, max_pairwise_correlation=0.3,
            is_well_diversified=True,
        )
        var_95 = VaRResult(
            confidence_level=0.95, method="historical",
            var_absolute=6000, var_percentage=0.06, cvar=0.08,
            holding_period=1, portfolio_value=100000,
        )
        level = self.service.assess_risk_level(div, var_95, [], [])
        assert level == "high"

    def test_assess_risk_level_medium_warning(self):
        div = DiversificationResult(
            diversification_ratio=1.5, effective_strategies=3.0,
            concentration_index=0.2, max_pairwise_correlation=0.3,
            is_well_diversified=True,
        )
        var_95 = VaRResult(
            confidence_level=0.95, method="historical",
            var_absolute=1000, var_percentage=0.01, cvar=0.015,
            holding_period=1, portfolio_value=100000,
        )
        alerts = [MLRiskAlert(
            strategy_name="A", alert_type="overfitting",
            severity="warning", metric_name="ic_decay_rate",
            metric_value=0.55, threshold=0.5,
            description="", detected_at=datetime(2026, 1, 1),
        )]
        level = self.service.assess_risk_level(div, var_95, [], alerts)
        assert level == "medium"

    def test_generate_recommendations_high_correlation(self):
        corr = CorrelationMatrix(
            strategy_names=["A", "B", "C"],
            matrix=[[1.0, 0.85, 0.2], [0.85, 1.0, 0.3], [0.2, 0.3, 1.0]],
        )
        div = DiversificationResult(
            diversification_ratio=1.5, effective_strategies=3.0,
            concentration_index=0.2, max_pairwise_correlation=0.85,
            is_well_diversified=True,
        )
        var_95 = VaRResult(
            confidence_level=0.95, method="historical",
            var_absolute=1000, var_percentage=0.01, cvar=0.015,
            holding_period=1, portfolio_value=100000,
        )
        recs = self.service.generate_recommendations(corr, div, var_95, [], [])
        assert any("相关性过高" in r for r in recs)

    def test_generate_recommendations_stress_fail(self):
        corr = CorrelationMatrix(
            strategy_names=["A"], matrix=[[1.0]],
        )
        div = DiversificationResult(
            diversification_ratio=1.0, effective_strategies=1.0,
            concentration_index=1.0, max_pairwise_correlation=0.0,
            is_well_diversified=False,
        )
        var_95 = VaRResult(
            confidence_level=0.95, method="historical",
            var_absolute=1000, var_percentage=0.01, cvar=0.015,
            holding_period=1, portfolio_value=100000,
        )
        stress = [StressTestResult(
            scenario_name="2015 股灾", scenario_type="historical",
            description="", portfolio_loss=-0.2, strategy_losses={},
            max_drawdown_under_stress=0.2, recovery_days=-1, passed=False,
        )]
        recs = self.service.generate_recommendations(corr, div, var_95, stress, [])
        assert any("2015 股灾" in r for r in recs)
