import pytest

from src.domain.portfolio.services.optimization.mean_variance_optimizer import (
    AssetInput,
    IndustryConstraint,
    MeanVarianceConfig,
    MeanVarianceOptimizer,
)


def _simple_cov(n: int, diag: float = 0.04, off_diag: float = 0.01) -> list[list[float]]:
    """构建简单的协方差矩阵。"""
    cov = [[off_diag] * n for _ in range(n)]
    for i in range(n):
        cov[i][i] = diag
    return cov


class TestMaxSharpe:
    def test_two_assets_higher_return_gets_more(self):
        assets = [
            AssetInput(name="A", expected_return=0.15, volatility=0.20),
            AssetInput(name="B", expected_return=0.08, volatility=0.20),
        ]
        cov = _simple_cov(2)
        opt = MeanVarianceOptimizer(assets=assets, covariance_matrix=cov)
        result = opt.optimize_max_sharpe()

        assert result.weights["A"] > result.weights["B"]
        assert result.weight_sum == pytest.approx(1.0, abs=1e-4)

    def test_weights_sum_to_one(self):
        assets = [
            AssetInput(name="A", expected_return=0.12, volatility=0.18),
            AssetInput(name="B", expected_return=0.10, volatility=0.22),
            AssetInput(name="C", expected_return=0.08, volatility=0.15),
        ]
        cov = _simple_cov(3)
        opt = MeanVarianceOptimizer(assets=assets, covariance_matrix=cov)
        result = opt.optimize_max_sharpe()

        assert result.weight_sum == pytest.approx(1.0, abs=1e-4)

    def test_single_asset_returns_full_weight(self):
        assets = [AssetInput(name="A", expected_return=0.10, volatility=0.20)]
        cov = [[0.04]]
        opt = MeanVarianceOptimizer(assets=assets, covariance_matrix=cov)
        result = opt.optimize_max_sharpe()

        assert result.weights["A"] == pytest.approx(1.0)
        assert result.expected_risk == pytest.approx(0.20)

    def test_sharpe_ratio_is_positive_for_good_assets(self):
        assets = [
            AssetInput(name="A", expected_return=0.15, volatility=0.20),
            AssetInput(name="B", expected_return=0.10, volatility=0.15),
        ]
        cov = _simple_cov(2)
        opt = MeanVarianceOptimizer(assets=assets, covariance_matrix=cov)
        result = opt.optimize_max_sharpe()

        assert result.sharpe_ratio > 0

    def test_result_has_correct_optimizer_name(self):
        assets = [AssetInput(name="A", expected_return=0.10, volatility=0.20)]
        cov = [[0.04]]
        opt = MeanVarianceOptimizer(assets=assets, covariance_matrix=cov)
        result = opt.optimize_max_sharpe()

        assert result.optimizer_name == "MeanVariance_SingleAsset"


class TestMinVariance:
    def test_lower_vol_asset_gets_more(self):
        assets = [
            AssetInput(name="A", expected_return=0.10, volatility=0.10),
            AssetInput(name="B", expected_return=0.10, volatility=0.30),
        ]
        cov = _simple_cov(2, diag=0.04, off_diag=0.005)
        cov[0][0] = 0.01
        cov[1][1] = 0.09
        opt = MeanVarianceOptimizer(assets=assets, covariance_matrix=cov)
        result = opt.optimize_min_variance()

        assert result.weights["A"] > result.weights["B"]
        assert result.weight_sum == pytest.approx(1.0, abs=1e-4)

    def test_min_variance_risk_is_lower_than_equal_weight(self):
        assets = [
            AssetInput(name="A", expected_return=0.10, volatility=0.10),
            AssetInput(name="B", expected_return=0.10, volatility=0.30),
        ]
        cov = [[0.01, 0.005], [0.005, 0.09]]
        opt = MeanVarianceOptimizer(assets=assets, covariance_matrix=cov)
        result = opt.optimize_min_variance()

        # 等权组合风险
        equal_risk = (0.25 * 0.01 + 0.25 * 0.09 + 2 * 0.25 * 0.005) ** 0.5
        assert result.expected_risk < equal_risk


class TestConstraints:
    def test_weight_bounds_respected(self):
        assets = [
            AssetInput(name="A", expected_return=0.20, volatility=0.15),
            AssetInput(name="B", expected_return=0.05, volatility=0.30),
        ]
        cov = _simple_cov(2)
        config = MeanVarianceConfig(min_weight=0.10, max_weight=0.70)
        opt = MeanVarianceOptimizer(
            assets=assets, covariance_matrix=cov, config=config
        )
        result = opt.optimize_max_sharpe()

        for w in result.weights.values():
            assert w >= 0.08  # slight tolerance for projection
            assert w <= 0.72

    def test_industry_constraint_limits_sector(self):
        assets = [
            AssetInput(name="bank_A", expected_return=0.12, volatility=0.20),
            AssetInput(name="bank_B", expected_return=0.11, volatility=0.20),
            AssetInput(name="tech_C", expected_return=0.15, volatility=0.25),
        ]
        cov = _simple_cov(3)
        industry = IndustryConstraint(
            industry_name="banking",
            asset_names=["bank_A", "bank_B"],
            max_weight=0.50,
        )
        opt = MeanVarianceOptimizer(
            assets=assets,
            covariance_matrix=cov,
            industry_constraints=[industry],
        )
        result = opt.optimize_max_sharpe()

        banking_weight = result.weights["bank_A"] + result.weights["bank_B"]
        assert banking_weight <= 0.52  # slight tolerance

    def test_different_risk_free_rates_produce_valid_results(self):
        """不同无风险利率下，优化器应产出有效的权重分配。"""
        assets = [
            AssetInput(name="A", expected_return=0.10, volatility=0.10),
            AssetInput(name="B", expected_return=0.12, volatility=0.30),
        ]
        cov = [[0.01, 0.005], [0.005, 0.09]]

        for rf in [0.01, 0.03, 0.08]:
            opt = MeanVarianceOptimizer(
                assets=assets,
                covariance_matrix=cov,
                config=MeanVarianceConfig(risk_free_rate=rf),
            )
            result = opt.optimize_max_sharpe()
            assert result.weight_sum == pytest.approx(1.0, abs=1e-4)
            assert all(w >= -1e-6 for w in result.weights.values())


class TestValidation:
    def test_empty_assets_raises(self):
        with pytest.raises(ValueError, match="assets must not be empty"):
            MeanVarianceOptimizer(assets=[], covariance_matrix=[])

    def test_covariance_dimension_mismatch_raises(self):
        assets = [AssetInput(name="A", expected_return=0.10, volatility=0.20)]
        with pytest.raises(ValueError, match="covariance_matrix rows"):
            MeanVarianceOptimizer(assets=assets, covariance_matrix=[[1, 2], [3, 4]])

    def test_covariance_row_length_mismatch_raises(self):
        assets = [
            AssetInput(name="A", expected_return=0.10, volatility=0.20),
            AssetInput(name="B", expected_return=0.08, volatility=0.15),
        ]
        with pytest.raises(ValueError, match="covariance_matrix row"):
            MeanVarianceOptimizer(
                assets=assets,
                covariance_matrix=[[0.04, 0.01], [0.01]],
            )
