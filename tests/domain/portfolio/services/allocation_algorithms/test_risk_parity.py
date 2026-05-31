from datetime import datetime

import pytest

from src.domain.portfolio.entities.strategy_performance import StrategyPerformance
from src.domain.portfolio.services.allocation_algorithms.risk_parity import RiskParityAlgorithm


def _perf(name: str, vol: float) -> StrategyPerformance:
    return StrategyPerformance(
        strategy_name=name,
        total_return=0.0,
        annualized_return=0.0,
        sharpe_ratio=0.0,
        max_drawdown=0.0,
        win_rate=0.0,
        volatility=vol,
        lookback_days=30,
        updated_at=datetime(2026, 1, 1),
    )


class TestRiskParityAlgorithm:
    def test_lower_vol_gets_more(self):
        algo = RiskParityAlgorithm()
        perfs = [_perf("A", vol=0.10), _perf("B", vol=0.30)]
        result = algo.calculate(100000.0, perfs)
        weights = {a.strategy_name: a.weight for a in result}
        assert weights["A"] > weights["B"]

    def test_weights_sum_to_one(self):
        algo = RiskParityAlgorithm()
        perfs = [_perf("A", vol=0.10), _perf("B", vol=0.20), _perf("C", vol=0.30)]
        result = algo.calculate(100000.0, perfs)
        total = sum(a.weight for a in result)
        assert total == pytest.approx(1.0, abs=1e-5)

    def test_equal_vol_equal_weight(self):
        algo = RiskParityAlgorithm()
        perfs = [_perf("A", vol=0.20), _perf("B", vol=0.20)]
        result = algo.calculate(100000.0, perfs)
        for a in result:
            assert a.weight == pytest.approx(0.5, abs=1e-5)

    def test_zero_vol_uses_min_floor(self):
        algo = RiskParityAlgorithm()
        perfs = [_perf("A", vol=0.0), _perf("B", vol=0.20)]
        result = algo.calculate(100000.0, perfs)
        total = sum(a.weight for a in result)
        assert total == pytest.approx(1.0, abs=1e-5)

    def test_empty_performances(self):
        algo = RiskParityAlgorithm()
        result = algo.calculate(100000.0, [])
        assert result == []
