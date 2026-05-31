"""组合优化应用服务。

协调组合优化器与资金分配引擎，将优化结果转换为策略分配。
"""

from dataclasses import dataclass
from datetime import datetime

from src.domain.portfolio.entities.strategy_allocation import StrategyAllocation
from src.domain.portfolio.entities.strategy_performance import StrategyPerformance
from src.domain.portfolio.services.capital_allocation_engine import CapitalAllocationEngine
from src.domain.portfolio.services.optimization.black_litterman_optimizer import (
    BlackLittermanOptimizer,
    InvestorView,
)
from src.domain.portfolio.services.optimization.mean_variance_optimizer import (
    AssetInput,
    IndustryConstraint,
    MeanVarianceConfig,
    MeanVarianceOptimizer,
)
from src.domain.portfolio.services.optimization.risk_budget_optimizer import (
    RiskBudgetInput,
    RiskBudgetOptimizer,
)
from src.domain.portfolio.value_objects.optimization_result import OptimizationResult


@dataclass(frozen=True, slots=True, kw_only=True)
class OptimizationRequest:
    """组合优化请求。

    Attributes:
        total_capital: 可分配总资金。
        performances: 各策略绩效数据。
        covariance_matrix: 策略间协方差矩阵。
        risk_free_rate: 无风险利率。
        optimizer_type: 优化器类型 ("max_sharpe", "min_variance", "risk_parity", "risk_budget", "black_litterman")。
        market_weights: Black-Litterman 市场均衡权重。
        investor_views: Black-Litterman 投资者观点。
        industry_constraints: 行业约束。
        risk_budgets: 风险预算比例。
    """

    total_capital: float
    performances: list[StrategyPerformance]
    covariance_matrix: list[list[float]]
    risk_free_rate: float = 0.03
    optimizer_type: str = "max_sharpe"
    market_weights: list[float] | None = None
    investor_views: list[InvestorView] | None = None
    industry_constraints: list[IndustryConstraint] | None = None
    risk_budgets: dict[str, float] | None = None


class PortfolioOptimizationAppService:
    """组合优化应用服务。

    将领域优化器与 CapitalAllocationEngine 集成，
    提供统一的组合优化入口。

    使用方式:
        service = PortfolioOptimizationAppService(allocation_engine)
        result = service.optimize(request)

    Args:
        allocation_engine: 资金分配引擎，用于约束和渐进调整。
    """

    def __init__(self, allocation_engine: CapitalAllocationEngine) -> None:
        self._engine = allocation_engine

    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        """执行组合优化。

        根据请求类型选择优化器，计算最优权重，
        然后通过 CapitalAllocationEngine 应用约束。

        Args:
            request: 优化请求。

        Returns:
            优化结果。
        """
        match request.optimizer_type:
            case "max_sharpe":
                result = self._optimize_max_sharpe(request)
            case "min_variance":
                result = self._optimize_min_variance(request)
            case "risk_parity":
                result = self._optimize_risk_parity(request)
            case "risk_budget":
                result = self._optimize_risk_budget(request)
            case "black_litterman":
                result = self._optimize_black_litterman(request)
            case _:
                raise ValueError(f"Unknown optimizer type: {request.optimizer_type}")

        return result

    def optimize_and_allocate(
        self,
        request: OptimizationRequest,
        current_date: datetime,
        current_allocations: list[StrategyAllocation] | None = None,
    ) -> OptimizationResult:
        """执行优化并将结果转换为资金分配。

        优化器计算权重后，通过 CapitalAllocationEngine 的约束机制
        （权重上下限、渐进调整）生成最终分配。

        Args:
            request: 优化请求。
            current_date: 当前日期。
            current_allocations: 当前分配。

        Returns:
            经约束调整后的优化结果。
        """
        raw_result = self.optimize(request)

        # 将优化权重转换为 StrategyAllocation
        allocations = [
            StrategyAllocation(
                strategy_name=name,
                allocated_capital=round(request.total_capital * weight, 2),
                weight=weight,
                allocated_at=current_date,
                reason=f"optimized:{request.optimizer_type}",
            )
            for name, weight in raw_result.weights.items()
        ]

        # 通过 engine 的约束机制调整
        constrained = self._engine._apply_constraints(allocations)
        if current_allocations:
            constrained = self._engine._apply_gradual_adjustment(
                constrained, current_allocations
            )

        # 重新计算调整后的收益和风险
        final_weights = {a.strategy_name: a.weight for a in constrained}

        adjusted_return = sum(
            final_weights.get(p.strategy_name, 0.0) * p.annualized_return
            for p in request.performances
        )
        adjusted_risk = self._estimate_portfolio_risk(
            final_weights, request.performances, request.covariance_matrix
        )
        adjusted_sharpe = (
            (adjusted_return - request.risk_free_rate) / adjusted_risk
            if adjusted_risk > 1e-15
            else 0.0
        )

        return OptimizationResult(
            weights=final_weights,
            expected_return=round(adjusted_return, 8),
            expected_risk=round(adjusted_risk, 8),
            sharpe_ratio=round(adjusted_sharpe, 8),
            optimizer_name=f"{raw_result.optimizer_name}_constrained",
        )

    def _optimize_max_sharpe(self, request: OptimizationRequest) -> OptimizationResult:
        """最大夏普比率优化。"""
        assets = [
            AssetInput(
                name=p.strategy_name,
                expected_return=p.annualized_return,
                volatility=p.volatility,
            )
            for p in request.performances
        ]
        config = MeanVarianceConfig(risk_free_rate=request.risk_free_rate)
        optimizer = MeanVarianceOptimizer(
            assets=assets,
            covariance_matrix=request.covariance_matrix,
            config=config,
            industry_constraints=request.industry_constraints,
        )
        return optimizer.optimize_max_sharpe()

    def _optimize_min_variance(self, request: OptimizationRequest) -> OptimizationResult:
        """最小方差优化。"""
        assets = [
            AssetInput(
                name=p.strategy_name,
                expected_return=p.annualized_return,
                volatility=p.volatility,
            )
            for p in request.performances
        ]
        config = MeanVarianceConfig(risk_free_rate=request.risk_free_rate)
        optimizer = MeanVarianceOptimizer(
            assets=assets,
            covariance_matrix=request.covariance_matrix,
            config=config,
            industry_constraints=request.industry_constraints,
        )
        return optimizer.optimize_min_variance()

    def _optimize_risk_parity(self, request: OptimizationRequest) -> OptimizationResult:
        """风险平价优化。"""
        assets = [
            RiskBudgetInput(
                name=p.strategy_name,
                expected_return=p.annualized_return,
                volatility=p.volatility,
            )
            for p in request.performances
        ]
        optimizer = RiskBudgetOptimizer(
            assets=assets,
            covariance_matrix=request.covariance_matrix,
        )
        return optimizer.optimize_risk_parity()

    def _optimize_risk_budget(self, request: OptimizationRequest) -> OptimizationResult:
        """风险预算优化。"""
        budget_map = request.risk_budgets or {}
        assets = [
            RiskBudgetInput(
                name=p.strategy_name,
                expected_return=p.annualized_return,
                volatility=p.volatility,
                risk_budget=budget_map.get(p.strategy_name),
            )
            for p in request.performances
        ]
        optimizer = RiskBudgetOptimizer(
            assets=assets,
            covariance_matrix=request.covariance_matrix,
        )
        return optimizer.optimize_risk_budget()

    def _optimize_black_litterman(self, request: OptimizationRequest) -> OptimizationResult:
        """Black-Litterman 优化。"""
        if request.market_weights is None:
            # 默认使用等权作为市场权重
            n = len(request.performances)
            market_weights = [1.0 / n] * n
        else:
            market_weights = request.market_weights

        asset_names = [p.strategy_name for p in request.performances]
        config = MeanVarianceConfig(risk_free_rate=request.risk_free_rate)

        optimizer = BlackLittermanOptimizer(
            asset_names=asset_names,
            market_weights=market_weights,
            covariance_matrix=request.covariance_matrix,
            risk_aversion=2.5,
            tau=0.05,
            views=request.investor_views,
            config=config,
        )
        return optimizer.optimize()

    @staticmethod
    def _estimate_portfolio_risk(
        weights: dict[str, float],
        performances: list[StrategyPerformance],
        covariance_matrix: list[list[float]],
    ) -> float:
        """估算组合风险（年化波动率）。"""
        names = [p.strategy_name for p in performances]
        w = [weights.get(name, 0.0) for name in names]
        n = len(names)
        port_var = 0.0
        for i in range(n):
            for j in range(n):
                port_var += w[i] * w[j] * covariance_matrix[i][j]
        return max(port_var, 0.0) ** 0.5
