import math
from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.risk.services.portfolio.correlation_analyzer import CorrelationAnalyzer
from src.domain.risk.services.portfolio.diversification_evaluator import DiversificationEvaluator
from src.domain.risk.services.portfolio.ml_model_risk_monitor import MLModelRiskMonitor
from src.domain.risk.services.portfolio.portfolio_var_calculator import PortfolioVaRCalculator
from src.domain.risk.services.portfolio.stress_test_runner import StressTestRunner
from src.domain.risk.value_objects.correlation_matrix import CorrelationMatrix
from src.domain.risk.value_objects.diversification_result import DiversificationResult
from src.domain.risk.value_objects.ml_risk_alert import MLRiskAlert
from src.domain.risk.value_objects.portfolio_risk_report import PortfolioRiskReport
from src.domain.risk.value_objects.stress_test_result import StressTestResult
from src.domain.risk.value_objects.var_result import VaRResult


class PortfolioRiskService:
    """组合风控服务 -- 聚合入口。

    协调相关性分析、分散度评估、VaR 计算、压力测试、ML 风险监控，
    生成综合的 PortfolioRiskReport。
    """

    def __init__(
        self,
        correlation_analyzer: CorrelationAnalyzer | None = None,
        diversification_evaluator: DiversificationEvaluator | None = None,
        var_calculator: PortfolioVaRCalculator | None = None,
        stress_test_runner: StressTestRunner | None = None,
        ml_risk_monitor: MLModelRiskMonitor | None = None,
        var_confidence_levels: list[float] | None = None,
    ) -> None:
        self._correlation = correlation_analyzer or CorrelationAnalyzer()
        self._diversification = diversification_evaluator or DiversificationEvaluator()
        self._var = var_calculator or PortfolioVaRCalculator()
        self._stress = stress_test_runner or StressTestRunner()
        self._ml_risk = ml_risk_monitor or MLModelRiskMonitor()
        self._confidence_levels = var_confidence_levels or [0.95, 0.99]

    def generate_report(
        self,
        strategy_reports: dict[str, BacktestReport],
        weights: dict[str, float],
        ml_data: dict[str, dict] | None = None,
    ) -> PortfolioRiskReport:
        """生成组合风控综合报告。

        Args:
            strategy_reports: {strategy_name: BacktestReport}。
            weights: {strategy_name: weight}。
            ml_data: 可选的 ML 模型数据，用于过拟合/漂移检测。
        """
        # 1. 计算相关性矩阵
        strategy_returns = {
            name: report.daily_returns for name, report in strategy_reports.items()
        }
        correlation = self._correlation.compute_correlation_matrix(strategy_returns)

        # 2. 计算各策略波动率（年化）
        volatilities: dict[str, float] = {}
        for name, returns in strategy_returns.items():
            if len(returns) < 2:
                volatilities[name] = 0.0
                continue
            mean_r = sum(returns) / len(returns)
            var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
            volatilities[name] = math.sqrt(var_r) * math.sqrt(252)

        # 3. 评估分散度
        diversification = self._diversification.evaluate(weights, volatilities, correlation)

        # 4. 计算组合收益率
        portfolio_returns = self._var.calculate_portfolio_returns(strategy_returns, weights)

        # 5. 计算组合总价值（取各策略最终资产加权）
        portfolio_value = sum(
            weights.get(name, 0.0) * report.final_capital
            for name, report in strategy_reports.items()
        )

        # 6. 计算 VaR
        var_95 = self._var.calculate_historical_var(
            portfolio_returns, portfolio_value, 0.95, 1
        )
        var_99 = self._var.calculate_historical_var(
            portfolio_returns, portfolio_value, 0.99, 1
        )

        # 7. 运行压力测试
        stress_tests = self._stress.run_all(strategy_reports, weights, correlation)

        # 8. ML 风险检查
        ml_alerts: list[MLRiskAlert] = []
        if ml_data:
            for name, data in ml_data.items():
                if "train_metrics" in data and "test_metrics" in data:
                    ml_alerts.extend(self._ml_risk.check_overfitting(
                        name, data["train_metrics"], data["test_metrics"]
                    ))
                if all(k in data for k in ["feature_name", "train_mean", "train_std", "online_mean", "online_std"]):
                    alert = self._ml_risk.check_feature_drift(
                        name, data["feature_name"],
                        data["train_mean"], data["train_std"],
                        data["online_mean"], data["online_std"],
                    )
                    if alert:
                        ml_alerts.append(alert)
                if "rolling_sharpe" in data:
                    ml_alerts.extend(self._ml_risk.check_performance_degradation(
                        name,
                        data.get("rolling_sharpe", []),
                        data.get("rolling_win_rate", []),
                        data.get("consecutive_loss_days", 0),
                    ))

        # 9. 综合评定风险等级
        risk_level = self.assess_risk_level(diversification, var_95, stress_tests, ml_alerts)

        # 10. 生成风险建议
        recommendations = self.generate_recommendations(
            correlation, diversification, var_95, stress_tests, ml_alerts
        )

        return PortfolioRiskReport(
            computed_at=datetime.now(),
            strategy_count=len(strategy_reports),
            correlation=correlation,
            diversification=diversification,
            var_95=var_95,
            var_99=var_99,
            stress_tests=stress_tests,
            ml_alerts=ml_alerts,
            overall_risk_level=risk_level,
            recommendations=recommendations,
        )

    def assess_risk_level(
        self,
        diversification: DiversificationResult,
        var_95: VaRResult,
        stress_tests: list[StressTestResult],
        ml_alerts: list[MLRiskAlert],
    ) -> str:
        """综合评定风险等级。

        规则：
        - critical: 任一压力测试不通过 OR 有 critical 级 ML 告警
        - high: VaR_95 > 5% OR 分散度不足 (HHI > 0.4)
        - medium: VaR_95 > 3% OR 有 warning 级 ML 告警
        - low: 其他情况
        """
        # critical
        if any(not t.passed for t in stress_tests):
            return "critical"
        if any(a.severity == "critical" for a in ml_alerts):
            return "critical"

        # high
        if var_95.var_percentage > 0.05:
            return "high"
        if diversification.concentration_index > 0.4:
            return "high"

        # medium
        if var_95.var_percentage > 0.03:
            return "medium"
        if any(a.severity == "warning" for a in ml_alerts):
            return "medium"

        return "low"

    def generate_recommendations(
        self,
        correlation: CorrelationMatrix,
        diversification: DiversificationResult,
        var_95: VaRResult,
        stress_tests: list[StressTestResult],
        ml_alerts: list[MLRiskAlert],
    ) -> list[str]:
        """生成风险建议。"""
        recs: list[str] = []

        # 相关性过高
        if correlation.max_correlation_pair[2] > 0.7:
            a, b, r = correlation.max_correlation_pair
            recs.append(f"策略 {a} 与 {b} 相关性过高({r:.2f})，建议替换其中一个或降低权重")

        # 分散效果不足
        if diversification.diversification_ratio < 1.1:
            recs.append("组合分散效果不足，建议增加低相关策略")

        # 资金过度集中
        if diversification.concentration_index > 0.35:
            names = correlation.strategy_names
            # 找到权重最大的策略
            if names:
                recs.append("资金过度集中，建议重新分配权重")

        # 压力测试不通过
        for t in stress_tests:
            if not t.passed:
                recs.append(f"{t.scenario_name} 场景下组合损失 {t.portfolio_loss:.1%}，超过阈值，建议降低仓位")

        # 过拟合告警
        for a in ml_alerts:
            if a.alert_type == "overfitting" and a.severity == "critical":
                recs.append(f"{a.strategy_name} 存在过拟合风险（{a.metric_name} {a.metric_value:.0%}），建议重新训练")

        # 特征漂移告警
        for a in ml_alerts:
            if a.alert_type == "feature_drift":
                recs.append(f"{a.strategy_name} 的特征发生漂移，建议检查数据源")

        # 表现退化告警
        for a in ml_alerts:
            if a.alert_type == "performance_degradation":
                recs.append(f"{a.strategy_name} 表现持续退化，建议暂停并评估")

        return recs
