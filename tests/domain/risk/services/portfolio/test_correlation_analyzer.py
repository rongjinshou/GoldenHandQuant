
from src.domain.risk.services.portfolio.correlation_analyzer import CorrelationAnalyzer


class TestCorrelationAnalyzer:
    def setup_method(self):
        self.analyzer = CorrelationAnalyzer()

    def test_perfect_positive_correlation(self):
        a = [0.01, 0.02, -0.01, 0.03, 0.01]
        b = [0.01, 0.02, -0.01, 0.03, 0.01]
        result = self.analyzer._pearson(a, b)
        assert abs(result - 1.0) < 1e-10

    def test_perfect_negative_correlation(self):
        a = [0.01, 0.02, -0.01, 0.03, 0.01]
        b = [-0.01, -0.02, 0.01, -0.03, -0.01]
        result = self.analyzer._pearson(a, b)
        assert abs(result - (-1.0)) < 1e-10

    def test_zero_correlation(self):
        a = [1.0, -1.0, 1.0, -1.0, 1.0]
        b = [1.0, 1.0, -1.0, -1.0, 0.0]
        result = self.analyzer._pearson(a, b)
        assert abs(result) < 0.5  # uncorrelated

    def test_pearson_empty_returns_zero(self):
        assert self.analyzer._pearson([], []) == 0.0

    def test_pearson_single_element_returns_zero(self):
        assert self.analyzer._pearson([1.0], [2.0]) == 0.0

    def test_pearson_constant_returns_zero(self):
        assert self.analyzer._pearson([1.0, 1.0, 1.0], [2.0, 3.0, 4.0]) == 0.0

    def test_compute_correlation_matrix_two_strategies(self):
        a = [0.01, 0.02, -0.01, 0.03, 0.01]
        b = [0.005, 0.015, -0.005, 0.025, 0.005]
        result = self.analyzer.compute_correlation_matrix({"A": a, "B": b})
        assert result.strategy_names == ["A", "B"]
        assert len(result.matrix) == 2
        assert result.matrix[0][0] == 1.0
        assert result.matrix[1][1] == 1.0
        assert abs(result.matrix[0][1] - result.matrix[1][0]) < 1e-10
        assert result.matrix[0][1] > 0.9  # highly correlated

    def test_compute_correlation_matrix_symmetric(self):
        a = [0.01, -0.02, 0.03, 0.01, -0.01]
        b = [0.02, 0.01, -0.01, 0.03, 0.02]
        c = [-0.01, 0.03, 0.01, -0.02, 0.01]
        result = self.analyzer.compute_correlation_matrix({"A": a, "B": b, "C": c})
        for i in range(3):
            for j in range(3):
                assert abs(result.matrix[i][j] - result.matrix[j][i]) < 1e-10

    def test_compute_correlation_matrix_empty(self):
        result = self.analyzer.compute_correlation_matrix({})
        assert result.strategy_names == []
        assert result.matrix == []
        assert result.sample_count == 0

    def test_rolling_correlation_basic(self):
        a = [0.01, 0.02, -0.01, 0.03, 0.01, 0.02, -0.02, 0.01]
        b = [0.005, 0.015, -0.005, 0.025, 0.005, 0.015, -0.015, 0.005]
        result = self.analyzer.compute_rolling_correlation(a, b, window=4)
        assert len(result) == 5  # 8 - 4 + 1
        assert all(-1 <= r <= 1 for r in result)

    def test_rolling_correlation_window_too_large(self):
        a = [0.01, 0.02, 0.03]
        b = [0.01, 0.02, 0.03]
        result = self.analyzer.compute_rolling_correlation(a, b, window=5)
        assert result == []

    def test_compute_correlation_matrix_sample_count(self):
        a = [0.01] * 100
        b = [0.02] * 100
        result = self.analyzer.compute_correlation_matrix({"A": a, "B": b})
        assert result.sample_count == 100
