import pytest

from src.domain.portfolio.value_objects.optimization_result import OptimizationResult


class TestOptimizationResult:
    def test_weight_sum(self):
        result = OptimizationResult(
            weights={"A": 0.4, "B": 0.35, "C": 0.25},
            expected_return=0.12,
            expected_risk=0.15,
            sharpe_ratio=0.6,
            optimizer_name="test",
        )
        assert result.weight_sum == pytest.approx(1.0)

    def test_asset_count_filters_near_zero(self):
        result = OptimizationResult(
            weights={"A": 0.5, "B": 0.5, "C": 1e-15},
            expected_return=0.10,
            expected_risk=0.12,
            sharpe_ratio=0.5,
            optimizer_name="test",
        )
        assert result.asset_count == 2

    def test_get_weight_existing(self):
        result = OptimizationResult(
            weights={"A": 0.6, "B": 0.4},
            expected_return=0.10,
            expected_risk=0.12,
            sharpe_ratio=0.5,
            optimizer_name="test",
        )
        assert result.get_weight("A") == pytest.approx(0.6)

    def test_get_weight_missing_returns_zero(self):
        result = OptimizationResult(
            weights={"A": 1.0},
            expected_return=0.10,
            expected_risk=0.12,
            sharpe_ratio=0.5,
            optimizer_name="test",
        )
        assert result.get_weight("B") == 0.0

    def test_immutable(self):
        result = OptimizationResult(
            weights={"A": 1.0},
            expected_return=0.10,
            expected_risk=0.12,
            sharpe_ratio=0.5,
            optimizer_name="test",
        )
        with pytest.raises(AttributeError):
            result.expected_return = 0.20  # type: ignore[misc]

    def test_empty_weights(self):
        result = OptimizationResult(
            weights={},
            expected_return=0.0,
            expected_risk=0.0,
            sharpe_ratio=0.0,
            optimizer_name="test",
        )
        assert result.weight_sum == 0.0
        assert result.asset_count == 0
