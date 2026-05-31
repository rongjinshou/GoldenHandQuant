from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.risk.services.portfolio.stress_scenarios.historical_scenarios import (
    StressScenario,
    get_historical_scenarios,
)
from src.domain.risk.services.portfolio.stress_scenarios.hypothetical_scenarios import (
    get_hypothetical_scenarios,
)
from src.domain.risk.value_objects.correlation_matrix import CorrelationMatrix
from src.domain.risk.value_objects.stress_test_result import StressTestResult


class StressTestRunner:
    """压力测试运行器。"""

    def __init__(
        self,
        historical_scenarios: list[StressScenario] | None = None,
        hypothetical_scenarios: list[StressScenario] | None = None,
        loss_threshold: float = 0.15,
    ) -> None:
        self._historical = (
            historical_scenarios if historical_scenarios is not None else get_historical_scenarios()
        )
        self._hypothetical = (
            hypothetical_scenarios if hypothetical_scenarios is not None else get_hypothetical_scenarios()
        )
        self._loss_threshold = loss_threshold

    def run_historical(
        self,
        strategy_reports: dict[str, BacktestReport],
        weights: dict[str, float],
    ) -> list[StressTestResult]:
        """运行历史场景压力测试。

        从各策略的 BacktestReport 中提取场景期间的收益率，
        按权重加权得到组合在该场景下的表现。
        """
        results: list[StressTestResult] = []
        for scenario in self._historical:
            if scenario.date_range is None:
                continue
            start, end = scenario.date_range
            strategy_losses: dict[str, float] = {}
            portfolio_loss = 0.0

            for name, report in strategy_reports.items():
                # 提取场景期间的收益率
                period_returns: list[float] = []
                for i, dt in enumerate(report.dates):
                    if start <= dt <= end and i < len(report.daily_returns):
                        period_returns.append(report.daily_returns[i])

                # 累计损失 = 乘积 (1+r) - 1
                cum = 1.0
                for r in period_returns:
                    cum *= (1.0 + r)
                loss = cum - 1.0
                strategy_losses[name] = loss
                portfolio_loss += weights.get(name, 0.0) * loss

            # 最大回撤：取策略中最大的回撤
            max_dd = 0.0
            for name, report in strategy_reports.items():
                if report.max_drawdown > max_dd:
                    max_dd = report.max_drawdown

            results.append(StressTestResult(
                scenario_name=scenario.name,
                scenario_type=scenario.scenario_type,
                description=scenario.description,
                portfolio_loss=portfolio_loss,
                strategy_losses=strategy_losses,
                max_drawdown_under_stress=max_dd,
                recovery_days=-1,
                passed=abs(portfolio_loss) < self._loss_threshold,
            ))
        return results

    def run_hypothetical(
        self,
        strategy_reports: dict[str, BacktestReport],
        weights: dict[str, float],
        correlation: CorrelationMatrix,
    ) -> list[StressTestResult]:
        """运行假设场景压力测试。"""
        results: list[StressTestResult] = []

        for scenario in self._hypothetical:
            params = scenario.shock_params
            strategy_losses: dict[str, float] = {}
            portfolio_loss = 0.0

            if "shock_factor" in params:
                # 市场暴跌：所有策略收益率同时乘以冲击系数
                shock = params["shock_factor"]
                for name, report in strategy_reports.items():
                    avg_ret = sum(report.daily_returns) / len(report.daily_returns) if report.daily_returns else 0.0
                    # 10 天的冲击
                    loss = shock + avg_ret * 10
                    strategy_losses[name] = loss
                    portfolio_loss += weights.get(name, 0.0) * loss

            elif "crisis_correlation" in params:
                # 相关性崩溃：假设所有策略同跌
                crisis_corr = params["crisis_correlation"]
                for name, report in strategy_reports.items():
                    vol = (
                        (sum(r**2 for r in report.daily_returns) / len(report.daily_returns))**0.5
                        if report.daily_returns else 0.0
                    )
                    # 相关性越高，组合波动越大
                    loss = -vol * 5 * crisis_corr
                    strategy_losses[name] = loss
                    portfolio_loss += weights.get(name, 0.0) * loss

            elif "liquidity_penalty" in params:
                # 流动性危机：高换手策略额外承受滑点惩罚
                penalty = params["liquidity_penalty"]
                for name, report in strategy_reports.items():
                    base_loss = -0.03  # 基础损失 3%
                    turnover_penalty = report.turnover_rate * penalty * 0.1
                    loss = base_loss - turnover_penalty
                    strategy_losses[name] = loss
                    portfolio_loss += weights.get(name, 0.0) * loss

            elif "loss_per_day" in params:
                # 单策略失效
                loss_per_day = params["loss_per_day"]
                duration = int(params.get("duration", 5))
                worst_name = max(
                    strategy_reports,
                    key=lambda n: strategy_reports[n].max_drawdown,
                )
                for name in strategy_reports:
                    if name == worst_name:
                        cum = 1.0
                        for _ in range(duration):
                            cum *= (1.0 + loss_per_day)
                        loss = cum - 1.0
                    else:
                        loss = 0.0
                    strategy_losses[name] = loss
                    portfolio_loss += weights.get(name, 0.0) * loss

            elif "duration" in params and "loss_per_day" not in params:
                # ML 模型失效：收益率为 0
                duration = int(params["duration"])
                for name, report in strategy_reports.items():
                    # 假设该策略在 duration 天内收益为 0，但机会成本 = 正常收益
                    avg_ret = sum(report.daily_returns) / len(report.daily_returns) if report.daily_returns else 0.0
                    opportunity_cost = avg_ret * duration
                    loss = opportunity_cost  # 相对于正常表现的损失
                    strategy_losses[name] = loss
                    portfolio_loss += weights.get(name, 0.0) * loss

            max_dd = max(
                (r.max_drawdown for r in strategy_reports.values()),
                default=0.0,
            )

            results.append(StressTestResult(
                scenario_name=scenario.name,
                scenario_type=scenario.scenario_type,
                description=scenario.description,
                portfolio_loss=portfolio_loss,
                strategy_losses=strategy_losses,
                max_drawdown_under_stress=max_dd,
                recovery_days=-1,
                passed=abs(portfolio_loss) < self._loss_threshold,
            ))
        return results

    def run_all(
        self,
        strategy_reports: dict[str, BacktestReport],
        weights: dict[str, float],
        correlation: CorrelationMatrix,
    ) -> list[StressTestResult]:
        """运行全部压力测试场景。"""
        historical = self.run_historical(strategy_reports, weights)
        hypothetical = self.run_hypothetical(strategy_reports, weights, correlation)
        return historical + hypothetical
