"""FactorAttributionService 单元测试。"""
import pytest

from src.domain.backtest.services.attribution.factor_attribution import (
    FactorAttributionService,
)


class TestFactorAttributionService:
    """因子归因分析测试。"""

    def setup_method(self):
        self.svc = FactorAttributionService()

    def test_basic_factor_attribution(self):
        """基本因子归因：2 个因子。"""
        result = self.svc.analyze(
            factor_names=["market", "size"],
            portfolio_exposures=[1.1, -0.3],
            benchmark_exposures=[1.0, 0.0],
            factor_returns=[0.05, 0.02],
            portfolio_return=0.08,
            benchmark_return=0.06,
        )

        # 因子 1 (market): spread = 1.1-1.0 = 0.1, contribution = 0.1*0.05 = 0.005
        assert abs(result.factor_contributions[0].contribution - 0.005) < 1e-6
        # 因子 2 (size): spread = -0.3-0.0 = -0.3, contribution = -0.3*0.02 = -0.006
        assert abs(result.factor_contributions[1].contribution - (-0.006)) < 1e-6
        # active_return = 0.08 - 0.06 = 0.02
        assert abs(result.active_return - 0.02) < 1e-6

    def test_residual_calculation(self):
        """残差 = 超额收益 - 因子解释部分。"""
        result = self.svc.analyze(
            factor_names=["market"],
            portfolio_exposures=[1.2],
            benchmark_exposures=[1.0],
            factor_returns=[0.05],
            portfolio_return=0.08,
            benchmark_return=0.06,
        )

        # 因子贡献 = (1.2-1.0)*0.05 = 0.01
        # 超额收益 = 0.02
        # 残差 = 0.02 - 0.01 = 0.01
        assert abs(result.residual_return - 0.01) < 1e-6

    def test_zero_residual(self):
        """当因子完全解释超额收益时，残差为零。"""
        result = self.svc.analyze(
            factor_names=["market"],
            portfolio_exposures=[1.2],
            benchmark_exposures=[1.0],
            factor_returns=[0.10],
            portfolio_return=0.12,
            benchmark_return=0.10,
        )

        # contribution = 0.2*0.10 = 0.02, active = 0.02, residual = 0
        assert abs(result.residual_return) < 1e-8

    def test_factor_spread(self):
        """验证因子利差计算。"""
        result = self.svc.analyze(
            factor_names=["value"],
            portfolio_exposures=[0.8],
            benchmark_exposures=[0.5],
            factor_returns=[0.03],
            portfolio_return=0.05,
            benchmark_return=0.04,
        )

        spread = result.factor_contributions[0]
        assert abs(spread.factor_spread - 0.3) < 1e-6
        assert spread.portfolio_exposure == 0.8
        assert spread.benchmark_exposure == 0.5
        assert spread.factor_return == 0.03

    def test_multiple_factors_detail(self):
        """多个因子的详细字段验证。"""
        result = self.svc.analyze(
            factor_names=["market", "size", "value", "momentum"],
            portfolio_exposures=[1.1, -0.2, 0.3, 0.5],
            benchmark_exposures=[1.0, 0.0, 0.1, 0.2],
            factor_returns=[0.05, 0.02, -0.01, 0.03],
            portfolio_return=0.10,
            benchmark_return=0.08,
        )

        assert len(result.factor_contributions) == 4
        assert result.factor_contributions[0].factor_name == "market"
        assert result.factor_contributions[3].factor_name == "momentum"

        # 验证总和关系
        explained = sum(f.contribution for f in result.factor_contributions)
        assert abs(result.active_return - explained - result.residual_return) < 1e-6

    def test_mismatched_lengths_raises(self):
        """输入列表长度不一致时应抛出 ValueError。"""
        with pytest.raises(ValueError, match="same length"):
            self.svc.analyze(
                factor_names=["market", "size"],
                portfolio_exposures=[1.1],
                benchmark_exposures=[1.0, 0.0],
                factor_returns=[0.05, 0.02],
                portfolio_return=0.08,
                benchmark_return=0.06,
            )

    def test_negative_factor_return(self):
        """因子收益率为负时也能正确计算。"""
        result = self.svc.analyze(
            factor_names=["market"],
            portfolio_exposures=[1.2],
            benchmark_exposures=[1.0],
            factor_returns=[-0.10],
            portfolio_return=0.05,
            benchmark_return=0.08,
        )

        # contribution = 0.2 * (-0.10) = -0.02
        assert abs(result.factor_contributions[0].contribution - (-0.02)) < 1e-6

    def test_total_and_benchmark_return_stored(self):
        """验证总收益率和基准收益率正确存储。"""
        result = self.svc.analyze(
            factor_names=["market"],
            portfolio_exposures=[1.0],
            benchmark_exposures=[1.0],
            factor_returns=[0.05],
            portfolio_return=0.08,
            benchmark_return=0.06,
        )

        assert result.total_return == 0.08
        assert result.benchmark_return == 0.06
