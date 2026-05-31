import math

from src.domain.risk.services.portfolio.diversification_evaluator import DiversificationEvaluator
from src.domain.risk.value_objects.correlation_matrix import CorrelationMatrix


class TestDiversificationEvaluator:
    def setup_method(self):
        self.evaluator = DiversificationEvaluator()

    def _make_correlation(self, names: list[str], corr: float) -> CorrelationMatrix:
        n = len(names)
        matrix = []
        for i in range(n):
            row = []
            for j in range(n):
                row.append(1.0 if i == j else corr)
            matrix.append(row)
        return CorrelationMatrix(strategy_names=names, matrix=matrix)

    def test_equal_weight_uncorrelated(self):
        """等权 3 策略、零相关：DR = sqrt(3)"""
        names = ["A", "B", "C"]
        weights = {"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}
        vols = {"A": 0.15, "B": 0.15, "C": 0.15}
        corr = self._make_correlation(names, 0.0)
        result = self.evaluator.evaluate(weights, vols, corr)
        # DR = sum(w*sigma) / sigma_p, sigma_p = sigma * sqrt(sum wi*wj*rho_ij)
        # rho_ii=1, rho_ij=0 => sigma_p = sigma * sqrt(sum wi^2) = 0.15 * sqrt(1/3)
        # DR = 0.15 / (0.15 * sqrt(1/3)) = sqrt(3)
        assert abs(result.diversification_ratio - math.sqrt(3)) < 0.01
        assert abs(result.effective_strategies - 3.0) < 0.01

    def test_equal_weight_perfect_correlation(self):
        """等权 3 策略、完全正相关：DR ≈ 1.0"""
        names = ["A", "B", "C"]
        weights = {"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}
        vols = {"A": 0.15, "B": 0.15, "C": 0.15}
        corr = self._make_correlation(names, 1.0)
        result = self.evaluator.evaluate(weights, vols, corr)
        assert abs(result.diversification_ratio - 1.0) < 0.01

    def test_single_strategy(self):
        """单策略：DR = 1.0, N_eff = 1.0"""
        names = ["A"]
        weights = {"A": 1.0}
        vols = {"A": 0.15}
        corr = self._make_correlation(names, 0.0)
        result = self.evaluator.evaluate(weights, vols, corr)
        assert abs(result.diversification_ratio - 1.0) < 0.01
        assert abs(result.effective_strategies - 1.0) < 0.01

    def test_hhi_concentrated(self):
        """90/5/5 分配：HHI = 0.815, N_eff = 1.23"""
        names = ["A", "B", "C"]
        weights = {"A": 0.9, "B": 0.05, "C": 0.05}
        vols = {"A": 0.15, "B": 0.15, "C": 0.15}
        corr = self._make_correlation(names, 0.0)
        result = self.evaluator.evaluate(weights, vols, corr)
        expected_hhi = 0.9**2 + 0.05**2 + 0.05**2
        assert abs(result.concentration_index - expected_hhi) < 0.001
        assert abs(result.effective_strategies - 1 / expected_hhi) < 0.01

    def test_is_well_diversified_true(self):
        """等权 5 策略、低相关 -> 充分分散 (HHI=0.2 < 0.25)"""
        names = ["A", "B", "C", "D", "E"]
        weights = {n: 0.2 for n in names}
        vols = {n: 0.15 for n in names}
        corr = self._make_correlation(names, 0.0)
        result = self.evaluator.evaluate(weights, vols, corr)
        assert result.is_well_diversified is True

    def test_is_well_diversified_false_concentrated(self):
        """高度集中 -> 不充分分散"""
        names = ["A", "B", "C"]
        weights = {"A": 0.9, "B": 0.05, "C": 0.05}
        vols = {"A": 0.15, "B": 0.15, "C": 0.15}
        corr = self._make_correlation(names, 0.0)
        result = self.evaluator.evaluate(weights, vols, corr)
        assert result.is_well_diversified is False
