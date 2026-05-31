"""BrinsonAttributionService 单元测试。"""
import pytest

from src.domain.backtest.services.attribution.brinson_attribution import (
    BrinsonAttributionService,
)


class TestBrinsonAttributionService:
    """Brinson 归因分析测试。"""

    def setup_method(self):
        self.svc = BrinsonAttributionService()

    def test_basic_attribution(self):
        """基本归因：2 个行业，验证各效应正确。"""
        result = self.svc.analyze(
            sector_names=["tech", "finance"],
            portfolio_weights=[0.6, 0.4],
            benchmark_weights=[0.5, 0.5],
            portfolio_returns=[0.10, 0.05],
            benchmark_returns=[0.08, 0.06],
        )

        # 配置效应: (0.6-0.5)*0.08 + (0.4-0.5)*0.06 = 0.008 + (-0.006) = 0.002
        assert abs(result.allocation_effect - 0.002) < 1e-6
        # 选择效应: 0.5*(0.10-0.08) + 0.5*(0.05-0.06) = 0.01 + (-0.005) = 0.005
        assert abs(result.selection_effect - 0.005) < 1e-6
        # 交互效应: (0.6-0.5)*(0.10-0.08) + (0.4-0.5)*(0.05-0.06)
        #         = 0.1*0.02 + (-0.1)*(-0.01) = 0.002 + 0.001 = 0.003
        assert abs(result.interaction_effect - 0.003) < 1e-6
        # 超额收益 = 0.002 + 0.005 + 0.003 = 0.01
        assert abs(result.active_return - 0.01) < 1e-6

    def test_total_and_benchmark_return(self):
        """验证组合总收益和基准总收益的加权计算。"""
        result = self.svc.analyze(
            sector_names=["A", "B"],
            portfolio_weights=[0.6, 0.4],
            benchmark_weights=[0.5, 0.5],
            portfolio_returns=[0.10, 0.05],
            benchmark_returns=[0.08, 0.06],
        )

        # total_return = 0.6*0.10 + 0.4*0.05 = 0.06 + 0.02 = 0.08
        assert abs(result.total_return - 0.08) < 1e-6
        # benchmark_return = 0.5*0.08 + 0.5*0.06 = 0.04 + 0.03 = 0.07
        assert abs(result.benchmark_return - 0.07) < 1e-6

    def test_effects_sum_equals_active_return(self):
        """三个效应之和应等于超额收益。"""
        result = self.svc.analyze(
            sector_names=["A", "B", "C"],
            portfolio_weights=[0.3, 0.5, 0.2],
            benchmark_weights=[0.4, 0.4, 0.2],
            portfolio_returns=[0.12, 0.08, -0.02],
            benchmark_returns=[0.10, 0.06, 0.00],
        )

        effects_sum = (
            result.allocation_effect
            + result.selection_effect
            + result.interaction_effect
        )
        assert abs(effects_sum - result.active_return) < 1e-6

    def test_zero_active_return(self):
        """组合与基准完全一致时，超额收益为零，各效应为零。"""
        result = self.svc.analyze(
            sector_names=["A"],
            portfolio_weights=[1.0],
            benchmark_weights=[1.0],
            portfolio_returns=[0.05],
            benchmark_returns=[0.05],
        )

        assert abs(result.active_return) < 1e-8
        assert abs(result.allocation_effect) < 1e-8
        assert abs(result.selection_effect) < 1e-8
        assert abs(result.interaction_effect) < 1e-8

    def test_sector_detail_count(self):
        """验证返回的行业明细数量正确。"""
        names = ["tech", "finance", "healthcare", "energy"]
        result = self.svc.analyze(
            sector_names=names,
            portfolio_weights=[0.25] * 4,
            benchmark_weights=[0.25] * 4,
            portfolio_returns=[0.10, 0.05, 0.08, -0.02],
            benchmark_returns=[0.08, 0.06, 0.07, 0.00],
        )

        assert len(result.sectors) == 4
        assert [s.name for s in result.sectors] == names

    def test_sector_row_fields(self):
        """验证单个行业行的字段正确。"""
        result = self.svc.analyze(
            sector_names=["tech"],
            portfolio_weights=[1.0],
            benchmark_weights=[1.0],
            portfolio_returns=[0.10],
            benchmark_returns=[0.08],
        )

        row = result.sectors[0]
        assert row.name == "tech"
        assert row.portfolio_weight == 1.0
        assert row.benchmark_weight == 1.0
        assert row.portfolio_return == 0.10
        assert row.benchmark_return == 0.08
        # allocation = (1.0-1.0)*0.08 = 0
        assert abs(row.allocation_effect) < 1e-8
        # selection = 1.0*(0.10-0.08) = 0.02
        assert abs(row.selection_effect - 0.02) < 1e-6
        # interaction = 0*0.02 = 0
        assert abs(row.interaction_effect) < 1e-8

    def test_mismatched_lengths_raises(self):
        """输入列表长度不一致时应抛出 ValueError。"""
        with pytest.raises(ValueError, match="same length"):
            self.svc.analyze(
                sector_names=["A", "B"],
                portfolio_weights=[0.5],
                benchmark_weights=[0.5, 0.5],
                portfolio_returns=[0.10, 0.05],
                benchmark_returns=[0.08, 0.06],
            )

    def test_negative_weights(self):
        """支持做空场景（负权重）。"""
        result = self.svc.analyze(
            sector_names=["long", "short"],
            portfolio_weights=[1.2, -0.2],
            benchmark_weights=[1.0, 0.0],
            portfolio_returns=[0.10, -0.05],
            benchmark_returns=[0.08, 0.00],
        )

        # 配置效应: (1.2-1.0)*0.08 + (-0.2-0.0)*0.00 = 0.016 + 0 = 0.016
        assert abs(result.allocation_effect - 0.016) < 1e-6
        # 选择效应: 1.0*(0.10-0.08) + 0.0*(-0.05-0.00) = 0.02 + 0 = 0.02
        assert abs(result.selection_effect - 0.02) < 1e-6

    def test_many_sectors(self):
        """大量行业也能正确处理。"""
        n = 20
        result = self.svc.analyze(
            sector_names=[f"sector_{i}" for i in range(n)],
            portfolio_weights=[1.0 / n] * n,
            benchmark_weights=[1.0 / n] * n,
            portfolio_returns=[0.01 * i for i in range(n)],
            benchmark_returns=[0.005 * i for i in range(n)],
        )

        assert len(result.sectors) == n
        effects_sum = (
            result.allocation_effect
            + result.selection_effect
            + result.interaction_effect
        )
        assert abs(effects_sum - result.active_return) < 1e-6
