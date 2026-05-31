import pytest

from src.domain.portfolio.services.optimization.risk_budget_optimizer import (
    RiskBudgetInput,
    RiskBudgetOptimizer,
)


def _cov_2x2(v1: float, v2: float, corr: float = 0.3) -> list[list[float]]:
    """构建 2x2 协方差矩阵。"""
    cov12 = corr * v1 * v2
    return [[v1 * v1, cov12], [cov12, v2 * v2]]


class TestRiskParity:
    def test_equal_vol_equal_contribution(self):
        """等波动率资产应有相等的风险贡献。"""
        assets = [
            RiskBudgetInput(name="A", expected_return=0.10, volatility=0.20),
            RiskBudgetInput(name="B", expected_return=0.08, volatility=0.20),
        ]
        cov = _cov_2x2(0.20, 0.20, corr=0.3)
        opt = RiskBudgetOptimizer(assets=assets, covariance_matrix=cov)
        result = opt.optimize_risk_parity()

        assert result.weights["A"] == pytest.approx(result.weights["B"], abs=1e-4)
        assert result.weight_sum == pytest.approx(1.0, abs=1e-4)

    def test_lower_vol_gets_higher_weight(self):
        """低波动率资产应获得更高权重（以实现等风险贡献）。"""
        assets = [
            RiskBudgetInput(name="A", expected_return=0.10, volatility=0.10),
            RiskBudgetInput(name="B", expected_return=0.10, volatility=0.30),
        ]
        cov = _cov_2x2(0.10, 0.30, corr=0.2)
        opt = RiskBudgetOptimizer(assets=assets, covariance_matrix=cov)
        result = opt.optimize_risk_parity()

        assert result.weights["A"] > result.weights["B"]

    def test_risk_contribution_equalized(self):
        """验证风险贡献近似相等。"""
        assets = [
            RiskBudgetInput(name="A", expected_return=0.10, volatility=0.15),
            RiskBudgetInput(name="B", expected_return=0.10, volatility=0.25),
            RiskBudgetInput(name="C", expected_return=0.10, volatility=0.20),
        ]
        cov = [
            [0.0225, 0.005, 0.003],
            [0.005, 0.0625, 0.008],
            [0.003, 0.008, 0.04],
        ]
        opt = RiskBudgetOptimizer(assets=assets, covariance_matrix=cov)
        result = opt.optimize_risk_parity()

        # 计算各资产的风险贡献
        w = [result.weights["A"], result.weights["B"], result.weights["C"]]
        # Sigma * w
        cov_w = [
            cov[0][0] * w[0] + cov[0][1] * w[1] + cov[0][2] * w[2],
            cov[1][0] * w[0] + cov[1][1] * w[1] + cov[1][2] * w[2],
            cov[2][0] * w[0] + cov[2][1] * w[1] + cov[2][2] * w[2],
        ]
        port_var = sum(w[i] * cov_w[i] for i in range(3))
        rc = [w[i] * cov_w[i] / port_var for i in range(3)]

        # 各资产风险贡献应接近 1/3
        for r in rc:
            assert r == pytest.approx(1.0 / 3, abs=0.05)

    def test_single_asset(self):
        assets = [RiskBudgetInput(name="A", expected_return=0.10, volatility=0.20)]
        cov = [[0.04]]
        opt = RiskBudgetOptimizer(assets=assets, covariance_matrix=cov)
        result = opt.optimize_risk_parity()

        assert result.weights["A"] == pytest.approx(1.0)


class TestRiskBudget:
    def test_custom_budget_proportions(self):
        """自定义风险预算应影响权重分配。"""
        assets = [
            RiskBudgetInput(name="A", expected_return=0.10, volatility=0.20, risk_budget=0.7),
            RiskBudgetInput(name="B", expected_return=0.10, volatility=0.20, risk_budget=0.3),
        ]
        cov = _cov_2x2(0.20, 0.20, corr=0.3)
        opt = RiskBudgetOptimizer(assets=assets, covariance_matrix=cov)
        result = opt.optimize_risk_budget()

        # A 有更高的风险预算，应有更高权重
        assert result.weights["A"] > result.weights["B"]
        assert result.weight_sum == pytest.approx(1.0, abs=1e-4)

    def test_budget_none_falls_back_to_equal(self):
        """未指定预算的资产应使用等风险分配。"""
        assets = [
            RiskBudgetInput(name="A", expected_return=0.10, volatility=0.20),
            RiskBudgetInput(name="B", expected_return=0.10, volatility=0.20),
        ]
        cov = _cov_2x2(0.20, 0.20, corr=0.3)
        opt = RiskBudgetOptimizer(assets=assets, covariance_matrix=cov)
        result_parity = opt.optimize_risk_parity()
        result_budget = opt.optimize_risk_budget()

        assert result_parity.weights["A"] == pytest.approx(
            result_budget.weights["A"], abs=1e-3
        )


class TestValidation:
    def test_empty_assets_raises(self):
        with pytest.raises(ValueError, match="assets must not be empty"):
            RiskBudgetOptimizer(assets=[], covariance_matrix=[])

    def test_covariance_dimension_mismatch_raises(self):
        assets = [RiskBudgetInput(name="A", expected_return=0.10, volatility=0.20)]
        with pytest.raises(ValueError, match="covariance_matrix rows"):
            RiskBudgetOptimizer(assets=assets, covariance_matrix=[[1, 2], [3, 4]])
