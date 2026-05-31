from datetime import datetime

import pytest

from src.domain.portfolio.entities.strategy_allocation import AllocationResult, StrategyAllocation


class TestStrategyAllocation:
    def test_create_valid_allocation(self):
        a = StrategyAllocation(
            strategy_name="test",
            allocated_capital=10000.0,
            weight=0.5,
            allocated_at=datetime(2026, 1, 1),
        )
        assert a.strategy_name == "test"
        assert a.allocated_capital == 10000.0
        assert a.weight == 0.5
        assert a.reason == ""

    def test_negative_capital_raises(self):
        with pytest.raises(ValueError, match="allocated_capital must be >= 0"):
            StrategyAllocation(
                strategy_name="test",
                allocated_capital=-1.0,
                weight=0.5,
                allocated_at=datetime(2026, 1, 1),
            )

    def test_weight_below_zero_raises(self):
        with pytest.raises(ValueError, match="weight must be in"):
            StrategyAllocation(
                strategy_name="test",
                allocated_capital=1000.0,
                weight=-0.1,
                allocated_at=datetime(2026, 1, 1),
            )

    def test_weight_above_one_raises(self):
        with pytest.raises(ValueError, match="weight must be in"):
            StrategyAllocation(
                strategy_name="test",
                allocated_capital=1000.0,
                weight=1.1,
                allocated_at=datetime(2026, 1, 1),
            )

    def test_zero_weight_valid(self):
        a = StrategyAllocation(
            strategy_name="test",
            allocated_capital=0.0,
            weight=0.0,
            allocated_at=datetime(2026, 1, 1),
        )
        assert a.weight == 0.0

    def test_max_weight_valid(self):
        a = StrategyAllocation(
            strategy_name="test",
            allocated_capital=100000.0,
            weight=1.0,
            allocated_at=datetime(2026, 1, 1),
        )
        assert a.weight == 1.0


class TestAllocationResult:
    def test_weight_sum(self):
        now = datetime(2026, 1, 1)
        allocs = [
            StrategyAllocation(strategy_name="A", allocated_capital=5000, weight=0.5, allocated_at=now),
            StrategyAllocation(strategy_name="B", allocated_capital=5000, weight=0.5, allocated_at=now),
        ]
        result = AllocationResult(
            total_capital=10000,
            allocations=allocs,
            algorithm="equal_weight",
            created_at=now,
        )
        assert result.weight_sum == pytest.approx(1.0)

    def test_weight_sum_with_three(self):
        now = datetime(2026, 1, 1)
        allocs = [
            StrategyAllocation(strategy_name="A", allocated_capital=3333, weight=0.333333, allocated_at=now),
            StrategyAllocation(strategy_name="B", allocated_capital=3333, weight=0.333333, allocated_at=now),
            StrategyAllocation(strategy_name="C", allocated_capital=3334, weight=0.333334, allocated_at=now),
        ]
        result = AllocationResult(
            total_capital=10000,
            allocations=allocs,
            algorithm="equal_weight",
            created_at=now,
        )
        assert result.weight_sum == pytest.approx(1.0, abs=1e-5)
