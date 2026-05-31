from datetime import datetime

import pytest

from src.domain.portfolio.entities.strategy_performance import StrategyPerformance
from src.domain.portfolio.services.allocation_algorithms.equal_weight import EqualWeightAlgorithm


def _perf(name: str) -> StrategyPerformance:
    return StrategyPerformance(
        strategy_name=name,
        total_return=0.0,
        annualized_return=0.0,
        sharpe_ratio=0.0,
        max_drawdown=0.0,
        win_rate=0.0,
        volatility=0.0,
        lookback_days=0,
        updated_at=datetime(2026, 1, 1),
    )


class TestEqualWeightAlgorithm:
    def test_two_strategies_equal_weight(self):
        algo = EqualWeightAlgorithm()
        perfs = [_perf("A"), _perf("B")]
        result = algo.calculate(100000.0, perfs)
        assert len(result) == 2
        assert result[0].weight == pytest.approx(0.5, abs=1e-5)
        assert result[1].weight == pytest.approx(0.5, abs=1e-5)

    def test_weights_sum_to_one(self):
        algo = EqualWeightAlgorithm()
        perfs = [_perf("A"), _perf("B"), _perf("C")]
        result = algo.calculate(100000.0, perfs)
        total = sum(a.weight for a in result)
        assert total == pytest.approx(1.0, abs=1e-5)

    def test_empty_performances(self):
        algo = EqualWeightAlgorithm()
        result = algo.calculate(100000.0, [])
        assert result == []

    def test_single_strategy(self):
        algo = EqualWeightAlgorithm()
        perfs = [_perf("A")]
        result = algo.calculate(100000.0, perfs)
        assert len(result) == 1
        assert result[0].weight == pytest.approx(1.0)

    def test_allocated_capital_proportional(self):
        algo = EqualWeightAlgorithm()
        perfs = [_perf("A"), _perf("B")]
        result = algo.calculate(100000.0, perfs)
        for a in result:
            assert a.allocated_capital == pytest.approx(50000.0, abs=1.0)
