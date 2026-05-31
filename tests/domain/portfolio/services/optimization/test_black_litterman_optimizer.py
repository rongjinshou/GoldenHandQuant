import pytest

from src.domain.portfolio.services.optimization.black_litterman_optimizer import (
    BlackLittermanOptimizer,
    InvestorView,
)


def _simple_cov(n: int, diag: float = 0.04, off_diag: float = 0.01) -> list[list[float]]:
    """构建简单的协方差矩阵。"""
    cov = [[off_diag] * n for _ in range(n)]
    for i in range(n):
        cov[i][i] = diag
    return cov


class TestBlackLittermanNoViews:
    def test_no_views_returns_equilibrium_weights(self):
        """无观点时应返回接近市场均衡的权重。"""
        names = ["A", "B"]
        market_w = [0.6, 0.4]
        cov = _simple_cov(2)

        opt = BlackLittermanOptimizer(
            asset_names=names,
            market_weights=market_w,
            covariance_matrix=cov,
        )
        result = opt.optimize()

        # 无观点时，结果应接近市场权重
        assert result.weights["A"] == pytest.approx(0.6, abs=0.15)
        assert result.weights["B"] == pytest.approx(0.4, abs=0.15)
        assert result.weight_sum == pytest.approx(1.0, abs=1e-4)

    def test_single_asset_no_views(self):
        names = ["A"]
        cov = [[0.04]]
        opt = BlackLittermanOptimizer(
            asset_names=names,
            market_weights=[1.0],
            covariance_matrix=cov,
        )
        result = opt.optimize()

        assert result.weights["A"] == pytest.approx(1.0)


class TestBlackLittermanWithViews:
    def test_positive_view_increases_weight(self):
        """对某资产的正面观点应增加其权重。"""
        names = ["A", "B"]
        market_w = [0.5, 0.5]
        cov = _simple_cov(2)

        views = [
            InvestorView(
                asset_weights={"A": 1.0},
                expected_return=0.15,  # A 的预期收益高于均衡
                confidence=0.8,
            )
        ]

        opt = BlackLittermanOptimizer(
            asset_names=names,
            market_weights=market_w,
            covariance_matrix=cov,
            views=views,
        )
        result = opt.optimize()

        assert result.weights["A"] > result.weights["B"]
        assert result.weight_sum == pytest.approx(1.0, abs=1e-4)

    def test_relative_view(self):
        """相对观点: A 比 B 高 5%。"""
        names = ["A", "B"]
        market_w = [0.5, 0.5]
        cov = _simple_cov(2)

        views = [
            InvestorView(
                asset_weights={"A": 1.0, "B": -1.0},
                expected_return=0.05,
                confidence=0.9,
            )
        ]

        opt = BlackLittermanOptimizer(
            asset_names=names,
            market_weights=market_w,
            covariance_matrix=cov,
            views=views,
        )
        result = opt.optimize()

        assert result.weights["A"] > result.weights["B"]

    def test_higher_confidence_moves_more(self):
        """更高置信度的观点对权重影响更大。"""
        names = ["A", "B"]
        market_w = [0.5, 0.5]
        cov = _simple_cov(2)

        view_low = InvestorView(
            asset_weights={"A": 1.0}, expected_return=0.20, confidence=0.2
        )
        view_high = InvestorView(
            asset_weights={"A": 1.0}, expected_return=0.20, confidence=0.95
        )

        opt_low = BlackLittermanOptimizer(
            asset_names=names,
            market_weights=market_w,
            covariance_matrix=cov,
            views=[view_low],
        )
        opt_high = BlackLittermanOptimizer(
            asset_names=names,
            market_weights=market_w,
            covariance_matrix=cov,
            views=[view_high],
        )
        result_low = opt_low.optimize()
        result_high = opt_high.optimize()

        # 高置信度下 A 权重应更高
        assert result_high.weights["A"] >= result_low.weights["A"]

    def test_multiple_views(self):
        """多个观点同时作用。"""
        names = ["A", "B", "C"]
        market_w = [1 / 3, 1 / 3, 1 / 3]
        cov = _simple_cov(3)

        views = [
            InvestorView(
                asset_weights={"A": 1.0}, expected_return=0.15, confidence=0.8
            ),
            InvestorView(
                asset_weights={"C": 1.0}, expected_return=0.20, confidence=0.9
            ),
        ]

        opt = BlackLittermanOptimizer(
            asset_names=names,
            market_weights=market_w,
            covariance_matrix=cov,
            views=views,
        )
        result = opt.optimize()

        # C 有最高观点收益，应有最高权重
        assert result.weights["C"] > result.weights["A"]
        assert result.weights["A"] > result.weights["B"]


class TestBlackLittermanValidation:
    def test_empty_asset_names_raises(self):
        with pytest.raises(ValueError, match="asset_names must not be empty"):
            BlackLittermanOptimizer(
                asset_names=[],
                market_weights=[],
                covariance_matrix=[],
            )

    def test_market_weights_dimension_mismatch_raises(self):
        with pytest.raises(ValueError, match="market_weights length"):
            BlackLittermanOptimizer(
                asset_names=["A", "B"],
                market_weights=[1.0],
                covariance_matrix=[[0.04, 0.01], [0.01, 0.04]],
            )

    def test_investor_view_confidence_validation(self):
        with pytest.raises(ValueError, match="confidence must be in"):
            InvestorView(asset_weights={"A": 1.0}, expected_return=0.10, confidence=0.0)

        with pytest.raises(ValueError, match="confidence must be in"):
            InvestorView(asset_weights={"A": 1.0}, expected_return=0.10, confidence=1.5)
