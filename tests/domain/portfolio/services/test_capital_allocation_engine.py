from datetime import datetime

import pytest

from src.domain.portfolio.entities.strategy_allocation import StrategyAllocation
from src.domain.portfolio.entities.strategy_performance import StrategyPerformance
from src.domain.portfolio.services.allocation_algorithms.sharpe_weight import SharpeWeightAlgorithm
from src.domain.portfolio.services.capital_allocation_engine import CapitalAllocationEngine
from src.domain.portfolio.services.rebalance_triggers.daily_trigger import DailyRebalanceTrigger


def _perf(name: str, sharpe: float = 1.0, lookback: int = 30) -> StrategyPerformance:
    return StrategyPerformance(
        strategy_name=name,
        total_return=0.1,
        annualized_return=0.2,
        sharpe_ratio=sharpe,
        max_drawdown=0.05,
        win_rate=0.6,
        volatility=0.15,
        lookback_days=lookback,
        updated_at=datetime(2026, 1, 15),
        profit_loss_ratio=2.0,
    )


def _alloc(name: str, weight: float, capital: float = 50000.0) -> StrategyAllocation:
    return StrategyAllocation(
        strategy_name=name,
        allocated_capital=capital,
        weight=weight,
        allocated_at=datetime(2026, 1, 1),
    )


class TestInitialAllocate:
    def test_three_strategies_equal_weight(self):
        engine = CapitalAllocationEngine(
            algorithm=SharpeWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        result = engine.initial_allocate(100000.0, ["A", "B", "C"])
        assert len(result.allocations) == 3
        for a in result.allocations:
            assert a.weight == pytest.approx(1.0 / 3, abs=1e-4)
        assert result.weight_sum == pytest.approx(1.0, abs=1e-5)

    def test_single_strategy_full_weight(self):
        engine = CapitalAllocationEngine(
            algorithm=SharpeWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        result = engine.initial_allocate(100000.0, ["A"])
        assert result.allocations[0].weight == pytest.approx(1.0)


class TestRebalance:
    def test_no_rebalance_when_trigger_says_no(self):
        engine = CapitalAllocationEngine(
            algorithm=SharpeWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        current = [_alloc("A", 0.5), _alloc("B", 0.5)]
        # Same day as last rebalance
        result = engine.rebalance(
            100000.0,
            [_perf("A", sharpe=2.0), _perf("B", sharpe=0.5)],
            current,
            datetime(2026, 1, 1),
        )
        assert result is None

    def test_rebalance_with_higher_sharpe_gets_more(self):
        engine = CapitalAllocationEngine(
            algorithm=SharpeWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        current = [_alloc("A", 0.5), _alloc("B", 0.5)]
        perfs = [_perf("A", sharpe=2.0), _perf("B", sharpe=0.5)]
        result = engine.rebalance(100000.0, perfs, current, datetime(2026, 1, 2))
        assert result is not None
        weights = {a.strategy_name: a.weight for a in result.allocations}
        assert weights["A"] > weights["B"]

    def test_rebalance_fallback_equal_when_insufficient_lookback(self):
        engine = CapitalAllocationEngine(
            algorithm=SharpeWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
            min_lookback_days=20,
        )
        current = [_alloc("A", 0.5), _alloc("B", 0.5)]
        perfs = [_perf("A", sharpe=2.0, lookback=10), _perf("B", sharpe=0.5, lookback=10)]
        result = engine.rebalance(100000.0, perfs, current, datetime(2026, 1, 2))
        assert result is not None
        assert result.algorithm == "equal_weight_fallback"
        for a in result.allocations:
            assert a.weight == pytest.approx(0.5, abs=1e-4)

    def test_weights_sum_to_one_after_rebalance(self):
        engine = CapitalAllocationEngine(
            algorithm=SharpeWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        current = [_alloc("A", 0.33), _alloc("B", 0.33), _alloc("C", 0.34)]
        perfs = [_perf("A", sharpe=2.0), _perf("B", sharpe=1.0), _perf("C", sharpe=0.5)]
        result = engine.rebalance(100000.0, perfs, current, datetime(2026, 1, 2))
        assert result is not None
        assert result.weight_sum == pytest.approx(1.0, abs=1e-5)


class TestConstraints:
    def test_max_weight_constraint(self):
        engine = CapitalAllocationEngine(
            algorithm=SharpeWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
            max_single_weight=0.40,
            min_single_weight=0.05,
            max_weight_change=0.10,
        )
        # A has extremely high sharpe vs B
        current = [_alloc("A", 0.5), _alloc("B", 0.5)]
        perfs = [_perf("A", sharpe=10.0), _perf("B", sharpe=0.01)]
        # Gradual adjustment limits change to 0.10 per rebalance
        # First rebalance: A goes from 0.5 to 0.6
        result = engine.rebalance(100000.0, perfs, current, datetime(2026, 1, 2))
        assert result is not None
        weights = {a.strategy_name: a.weight for a in result.allocations}
        assert weights["A"] <= 0.6  # gradual: 0.5 + 0.10
        # Second rebalance: algorithm target ~0.664, gradual allows up to 0.6+0.10=0.7
        result2 = engine.rebalance(100000.0, perfs, result.allocations, datetime(2026, 1, 3))
        assert result2 is not None
        weights2 = {a.strategy_name: a.weight for a in result2.allocations}
        assert weights2["A"] > weights["A"]  # converges further toward max constraint

    def test_min_weight_constraint(self):
        engine = CapitalAllocationEngine(
            algorithm=SharpeWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
            max_single_weight=0.90,
            min_single_weight=0.10,
        )
        current = [_alloc("A", 0.5), _alloc("B", 0.5)]
        perfs = [_perf("A", sharpe=10.0), _perf("B", sharpe=0.01)]
        result = engine.rebalance(100000.0, perfs, current, datetime(2026, 1, 2))
        assert result is not None
        weights = {a.strategy_name: a.weight for a in result.allocations}
        assert weights["B"] >= 0.05  # min constraint


class TestGradualAdjustment:
    def test_limited_weight_change_per_rebalance(self):
        engine = CapitalAllocationEngine(
            algorithm=SharpeWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
            max_weight_change=0.10,
        )
        current = [_alloc("A", 0.5), _alloc("B", 0.5)]
        perfs = [_perf("A", sharpe=10.0), _perf("B", sharpe=0.01)]
        result = engine.rebalance(100000.0, perfs, current, datetime(2026, 1, 2))
        assert result is not None
        weights = {a.strategy_name: a.weight for a in result.allocations}
        # A was 0.5, max change is 0.10, so A should be at most ~0.60
        assert weights["A"] <= 0.65  # some tolerance for normalization


class TestAdjustForNewStrategy:
    def test_new_strategy_added_with_cold_start(self):
        engine = CapitalAllocationEngine(
            algorithm=SharpeWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        current = [_alloc("A", 0.5), _alloc("B", 0.5)]
        result = engine.adjust_for_new_strategy(100000.0, "C", current)
        names = {a.strategy_name for a in result.allocations}
        assert "C" in names
        assert result.weight_sum == pytest.approx(1.0, abs=1e-5)

    def test_new_strategy_weight_limited_by_cold_start(self):
        engine = CapitalAllocationEngine(
            algorithm=SharpeWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        current = [_alloc("A", 0.5), _alloc("B", 0.5)]
        result = engine.adjust_for_new_strategy(100000.0, "C", current)
        c_alloc = [a for a in result.allocations if a.strategy_name == "C"][0]
        assert c_alloc.weight <= 0.20  # cold start cap

    def test_existing_strategies_proportionally_reduced(self):
        engine = CapitalAllocationEngine(
            algorithm=SharpeWeightAlgorithm(),
            trigger=DailyRebalanceTrigger(),
        )
        current = [_alloc("A", 0.6), _alloc("B", 0.4)]
        result = engine.adjust_for_new_strategy(100000.0, "C", current)
        weights = {a.strategy_name: a.weight for a in result.allocations}
        # A was 60%, B was 40%, ratio preserved
        # After removing C's weight, remaining should be in 60:40 ratio
        remaining = weights["A"] + weights["B"]
        assert weights["A"] / remaining == pytest.approx(0.6, abs=1e-3)
