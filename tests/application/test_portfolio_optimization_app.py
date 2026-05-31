from datetime import datetime

import pytest

from src.application.portfolio_optimization_app import (
    OptimizationRequest,
    PortfolioOptimizationAppService,
)
from src.domain.portfolio.entities.strategy_allocation import StrategyAllocation
from src.domain.portfolio.entities.strategy_performance import StrategyPerformance
from src.domain.portfolio.services.allocation_algorithms.equal_weight import (
    EqualWeightAlgorithm,
)
from src.domain.portfolio.services.capital_allocation_engine import CapitalAllocationEngine
from src.domain.portfolio.services.optimization.black_litterman_optimizer import (
    InvestorView,
)
from src.domain.portfolio.services.rebalance_triggers.daily_trigger import (
    DailyRebalanceTrigger,
)


def _perf(name: str, ret: float = 0.12, vol: float = 0.20) -> StrategyPerformance:
    return StrategyPerformance(
        strategy_name=name,
        total_return=ret,
        annualized_return=ret,
        sharpe_ratio=ret / vol if vol > 0 else 0.0,
        max_drawdown=0.10,
        win_rate=0.55,
        volatility=vol,
        lookback_days=60,
        updated_at=datetime(2026, 5, 1),
    )


def _alloc(name: str, weight: float) -> StrategyAllocation:
    return StrategyAllocation(
        strategy_name=name,
        allocated_capital=round(100000 * weight, 2),
        weight=weight,
        allocated_at=datetime(2026, 1, 1),
    )


def _cov_3x3() -> list[list[float]]:
    return [
        [0.04, 0.01, 0.005],
        [0.01, 0.0625, 0.008],
        [0.005, 0.008, 0.0225],
    ]


class TestOptimize:
    def test_max_sharpe_returns_result(self):
        engine = CapitalAllocationEngine(
            algorithm=EqualWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        service = PortfolioOptimizationAppService(engine)
        request = OptimizationRequest(
            total_capital=100000.0,
            performances=[_perf("A", 0.15, 0.20), _perf("B", 0.08, 0.15)],
            covariance_matrix=[[0.04, 0.01], [0.01, 0.0225]],
            optimizer_type="max_sharpe",
        )
        result = service.optimize(request)

        assert result.weight_sum == pytest.approx(1.0, abs=1e-3)
        assert result.weights["A"] > result.weights["B"]

    def test_min_variance_returns_result(self):
        engine = CapitalAllocationEngine(
            algorithm=EqualWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        service = PortfolioOptimizationAppService(engine)
        request = OptimizationRequest(
            total_capital=100000.0,
            performances=[_perf("A", 0.10, 0.10), _perf("B", 0.10, 0.30)],
            covariance_matrix=[[0.01, 0.005], [0.005, 0.09]],
            optimizer_type="min_variance",
        )
        result = service.optimize(request)

        assert result.weights["A"] > result.weights["B"]

    def test_risk_parity_returns_result(self):
        engine = CapitalAllocationEngine(
            algorithm=EqualWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        service = PortfolioOptimizationAppService(engine)
        request = OptimizationRequest(
            total_capital=100000.0,
            performances=[_perf("A", 0.10, 0.15), _perf("B", 0.10, 0.30)],
            covariance_matrix=[[0.0225, 0.005], [0.005, 0.09]],
            optimizer_type="risk_parity",
        )
        result = service.optimize(request)

        assert result.weights["A"] > result.weights["B"]

    def test_risk_budget_returns_result(self):
        engine = CapitalAllocationEngine(
            algorithm=EqualWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        service = PortfolioOptimizationAppService(engine)
        request = OptimizationRequest(
            total_capital=100000.0,
            performances=[_perf("A", 0.10, 0.20), _perf("B", 0.10, 0.20)],
            covariance_matrix=[[0.04, 0.01], [0.01, 0.04]],
            optimizer_type="risk_budget",
            risk_budgets={"A": 0.7, "B": 0.3},
        )
        result = service.optimize(request)

        assert result.weights["A"] > result.weights["B"]

    def test_black_litterman_returns_result(self):
        engine = CapitalAllocationEngine(
            algorithm=EqualWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        service = PortfolioOptimizationAppService(engine)
        views = [
            InvestorView(
                asset_weights={"A": 1.0}, expected_return=0.20, confidence=0.8
            )
        ]
        request = OptimizationRequest(
            total_capital=100000.0,
            performances=[_perf("A", 0.12, 0.20), _perf("B", 0.08, 0.15)],
            covariance_matrix=[[0.04, 0.01], [0.01, 0.0225]],
            optimizer_type="black_litterman",
            market_weights=[0.5, 0.5],
            investor_views=views,
        )
        result = service.optimize(request)

        assert result.weights["A"] > result.weights["B"]
        assert result.weight_sum == pytest.approx(1.0, abs=1e-3)

    def test_unknown_optimizer_type_raises(self):
        engine = CapitalAllocationEngine(
            algorithm=EqualWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        service = PortfolioOptimizationAppService(engine)
        request = OptimizationRequest(
            total_capital=100000.0,
            performances=[_perf("A")],
            covariance_matrix=[[0.04]],
            optimizer_type="unknown",
        )
        with pytest.raises(ValueError, match="Unknown optimizer type"):
            service.optimize(request)


class TestOptimizeAndAllocate:
    def test_constrained_result_weights_sum_to_one(self):
        engine = CapitalAllocationEngine(
            algorithm=EqualWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
            max_single_weight=0.60,
            min_single_weight=0.05,
            max_weight_change=1.0,  # 不限制渐进调整
        )
        service = PortfolioOptimizationAppService(engine)
        request = OptimizationRequest(
            total_capital=100000.0,
            performances=[
                _perf("A", 0.15, 0.20),
                _perf("B", 0.08, 0.15),
                _perf("C", 0.05, 0.25),
            ],
            covariance_matrix=_cov_3x3(),
            optimizer_type="max_sharpe",
        )
        result = service.optimize_and_allocate(
            request, current_date=datetime(2026, 6, 1)
        )

        assert result.weight_sum == pytest.approx(1.0, abs=1e-3)
        for w in result.weights.values():
            assert w >= 0.0
            assert w <= 1.0

    def test_with_current_allocations_applies_gradual_adjustment(self):
        engine = CapitalAllocationEngine(
            algorithm=EqualWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
            max_weight_change=0.10,
        )
        service = PortfolioOptimizationAppService(engine)
        current = [_alloc("A", 0.5), _alloc("B", 0.5)]
        request = OptimizationRequest(
            total_capital=100000.0,
            performances=[_perf("A", 0.20, 0.15), _perf("B", 0.05, 0.30)],
            covariance_matrix=[[0.0225, 0.005], [0.005, 0.09]],
            optimizer_type="max_sharpe",
        )
        result = service.optimize_and_allocate(
            request,
            current_date=datetime(2026, 6, 2),
            current_allocations=current,
        )

        # 渐进调整应限制权重变化
        assert result.weights["A"] <= 0.65

    def test_result_has_constrained_suffix(self):
        engine = CapitalAllocationEngine(
            algorithm=EqualWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        service = PortfolioOptimizationAppService(engine)
        request = OptimizationRequest(
            total_capital=100000.0,
            performances=[_perf("A"), _perf("B")],
            covariance_matrix=[[0.04, 0.01], [0.01, 0.04]],
            optimizer_type="risk_parity",
        )
        result = service.optimize_and_allocate(
            request, current_date=datetime(2026, 6, 1)
        )

        assert "constrained" in result.optimizer_name
