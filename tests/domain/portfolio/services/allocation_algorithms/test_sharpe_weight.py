from datetime import datetime

import pytest

from src.domain.portfolio.entities.strategy_performance import StrategyPerformance
from src.domain.portfolio.services.allocation_algorithms.sharpe_weight import SharpeWeightAlgorithm


def _perf(name: str, sharpe: float) -> StrategyPerformance:
    return StrategyPerformance(
        strategy_name=name,
        total_return=0.0,
        annualized_return=0.0,
        sharpe_ratio=sharpe,
        max_drawdown=0.0,
        win_rate=0.0,
        volatility=0.0,
        lookback_days=30,
        updated_at=datetime(2026, 1, 1),
    )


class TestSharpeWeightAlgorithm:
    def test_higher_sharpe_gets_more(self):
        algo = SharpeWeightAlgorithm()
        perfs = [_perf("A", sharpe=2.0), _perf("B", sharpe=0.5)]
        result = algo.calculate(100000.0, perfs)
        weights = {a.strategy_name: a.weight for a in result}
        assert weights["A"] > weights["B"]

    def test_weights_sum_to_one(self):
        algo = SharpeWeightAlgorithm()
        perfs = [_perf("A", sharpe=2.0), _perf("B", sharpe=0.5), _perf("C", sharpe=1.0)]
        result = algo.calculate(100000.0, perfs)
        total = sum(a.weight for a in result)
        assert total == pytest.approx(1.0, abs=1e-5)

    def test_zero_sharpe_still_gets_weight(self):
        """全零夏普时 epsilon 保证每个策略都有权重。"""
        algo = SharpeWeightAlgorithm()
        perfs = [_perf("A", sharpe=0.0), _perf("B", sharpe=0.0)]
        result = algo.calculate(100000.0, perfs)
        for a in result:
            assert a.weight == pytest.approx(0.5, abs=1e-5)

    def test_negative_sharpe_clamped_to_zero(self):
        algo = SharpeWeightAlgorithm()
        perfs = [_perf("A", sharpe=-1.0), _perf("B", sharpe=1.0)]
        result = algo.calculate(100000.0, perfs)
        weights = {a.strategy_name: a.weight for a in result}
        # A: max(-1,0)+0.01 = 0.01, B: max(1,0)+0.01 = 1.01
        assert weights["B"] > weights["A"]
        assert weights["B"] > 0.9

    def test_empty_performances(self):
        algo = SharpeWeightAlgorithm()
        result = algo.calculate(100000.0, [])
        assert result == []
