from datetime import datetime

import pytest

from src.domain.portfolio.entities.strategy_performance import StrategyPerformance
from src.domain.portfolio.services.allocation_algorithms.kelly_allocation import KellyAllocationAlgorithm


def _perf(name: str, win_rate: float = 0.5, pl_ratio: float = 2.0) -> StrategyPerformance:
    return StrategyPerformance(
        strategy_name=name,
        total_return=0.0,
        annualized_return=0.0,
        sharpe_ratio=0.0,
        max_drawdown=0.0,
        win_rate=win_rate,
        volatility=0.0,
        lookback_days=30,
        updated_at=datetime(2026, 1, 1),
        profit_loss_ratio=pl_ratio,
    )


class TestKellyAllocationAlgorithm:
    def test_higher_win_rate_gets_more(self):
        algo = KellyAllocationAlgorithm()
        perfs = [_perf("A", win_rate=0.7, pl_ratio=2.0), _perf("B", win_rate=0.4, pl_ratio=2.0)]
        result = algo.calculate(100000.0, perfs)
        weights = {a.strategy_name: a.weight for a in result}
        assert weights["A"] > weights["B"]

    def test_weights_sum_to_one(self):
        algo = KellyAllocationAlgorithm()
        perfs = [_perf("A", win_rate=0.6), _perf("B", win_rate=0.5), _perf("C", win_rate=0.4)]
        result = algo.calculate(100000.0, perfs)
        total = sum(a.weight for a in result)
        assert total == pytest.approx(1.0, abs=1e-5)

    def test_zero_pl_ratio_fallback_equal(self):
        """盈亏比为 0 时回退等权。"""
        algo = KellyAllocationAlgorithm()
        perfs = [_perf("A", win_rate=0.5, pl_ratio=0.0), _perf("B", win_rate=0.5, pl_ratio=0.0)]
        result = algo.calculate(100000.0, perfs)
        for a in result:
            assert a.weight == pytest.approx(0.5, abs=1e-5)
            assert a.reason == "kelly_fallback_equal"

    def test_negative_kelly_clamped_to_zero(self):
        """亏损策略凯利值为 0，权重也为 0（但回退等权）。"""
        algo = KellyAllocationAlgorithm()
        # win_rate=0.3, pl_ratio=1.0 => kelly = (0.3*1 - 0.7)/1 = -0.4 -> 0
        perfs = [_perf("A", win_rate=0.3, pl_ratio=1.0), _perf("B", win_rate=0.3, pl_ratio=1.0)]
        result = algo.calculate(100000.0, perfs)
        # Both kelly = 0, fallback to equal
        for a in result:
            assert a.weight == pytest.approx(0.5, abs=1e-5)

    def test_half_kelly_fraction(self):
        """验证半凯利约束。"""
        algo = KellyAllocationAlgorithm()
        assert algo.KELLY_FRACTION == 0.5

    def test_empty_performances(self):
        algo = KellyAllocationAlgorithm()
        result = algo.calculate(100000.0, [])
        assert result == []
