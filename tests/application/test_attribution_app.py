"""AttributionAppService 单元测试。"""
from datetime import datetime

from src.application.attribution_app import AttributionAppService
from src.domain.backtest.entities.backtest_report import BacktestReport


def _make_report(
    name: str = "test_strategy",
    total_return: float = 0.08,
    initial_capital: float = 100_000.0,
) -> BacktestReport:
    """构造测试用 BacktestReport。"""
    return BacktestReport(
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        initial_capital=initial_capital,
        final_capital=initial_capital * (1 + total_return),
        total_return=total_return,
        annualized_return=total_return,
        max_drawdown=0.05,
        win_rate=0.55,
        profit_loss_ratio=1.5,
        trade_count=20,
        strategy_name=name,
    )


class TestAttributionAppService:
    """归因应用服务测试。"""

    def setup_method(self):
        self.svc = AttributionAppService()

    def test_run_brinson_attribution(self):
        """Brinson 归因通过应用服务正确执行。"""
        result = self.svc.run_brinson_attribution(
            strategy_name="test",
            sector_names=["tech", "finance"],
            portfolio_weights=[0.6, 0.4],
            benchmark_weights=[0.5, 0.5],
            portfolio_returns=[0.10, 0.05],
            benchmark_returns=[0.08, 0.06],
        )

        assert abs(result.allocation_effect - 0.002) < 1e-6
        assert abs(result.selection_effect - 0.005) < 1e-6
        assert len(result.sectors) == 2

    def test_run_factor_attribution(self):
        """因子归因通过应用服务正确执行。"""
        result = self.svc.run_factor_attribution(
            factor_names=["market", "size"],
            portfolio_exposures=[1.1, -0.3],
            benchmark_exposures=[1.0, 0.0],
            factor_returns=[0.05, 0.02],
            portfolio_return=0.08,
            benchmark_return=0.06,
        )

        assert len(result.factor_contributions) == 2
        assert abs(result.active_return - 0.02) < 1e-6

    def test_generate_attribution_report_brinson_only(self):
        """仅 Brinson 归因的报告生成。"""
        report = _make_report()
        result = self.svc.generate_attribution_report(
            report=report,
            sector_names=["tech", "finance"],
            portfolio_weights=[0.6, 0.4],
            benchmark_weights=[0.5, 0.5],
            portfolio_returns=[0.10, 0.05],
            benchmark_returns=[0.08, 0.06],
        )

        assert result.strategy_name == "test_strategy"
        assert result.brinson_detail is not None
        assert result.factor_detail is None
        assert result.factor_contributions == {}

    def test_generate_attribution_report_with_factors(self):
        """包含因子归因的完整报告生成。"""
        report = _make_report()
        result = self.svc.generate_attribution_report(
            report=report,
            sector_names=["tech"],
            portfolio_weights=[1.0],
            benchmark_weights=[1.0],
            portfolio_returns=[0.08],
            benchmark_returns=[0.06],
            factor_names=["market"],
            portfolio_exposures=[1.1],
            benchmark_exposures=[1.0],
            factor_returns=[0.05],
            benchmark_total_return=0.06,
        )

        assert result.brinson_detail is not None
        assert result.factor_detail is not None
        assert "market" in result.factor_contributions

    def test_generate_attribution_report_persists(self):
        """报告生成后存储在 reports 列表中。"""
        report = _make_report()
        assert len(self.svc.reports) == 0

        self.svc.generate_attribution_report(
            report=report,
            sector_names=["tech"],
            portfolio_weights=[1.0],
            benchmark_weights=[1.0],
            portfolio_returns=[0.08],
            benchmark_returns=[0.06],
        )

        assert len(self.svc.reports) == 1
        assert self.svc.reports[0].strategy_name == "test_strategy"

    def test_prepare_visualization_data_basic(self):
        """可视化数据结构正确。"""
        report = _make_report()
        attr_report = self.svc.generate_attribution_report(
            report=report,
            sector_names=["tech", "finance"],
            portfolio_weights=[0.6, 0.4],
            benchmark_weights=[0.5, 0.5],
            portfolio_returns=[0.10, 0.05],
            benchmark_returns=[0.08, 0.06],
        )

        viz = self.svc.prepare_visualization_data(attr_report)

        assert viz["strategy_name"] == "test_strategy"
        assert "summary" in viz
        assert "brinson_chart" in viz
        assert len(viz["brinson_chart"]["categories"]) == 4
        assert len(viz["brinson_chart"]["values"]) == 4

    def test_prepare_visualization_data_with_sectors(self):
        """包含行业明细的可视化数据。"""
        report = _make_report()
        attr_report = self.svc.generate_attribution_report(
            report=report,
            sector_names=["tech", "finance"],
            portfolio_weights=[0.6, 0.4],
            benchmark_weights=[0.5, 0.5],
            portfolio_returns=[0.10, 0.05],
            benchmark_returns=[0.08, 0.06],
        )

        viz = self.svc.prepare_visualization_data(attr_report)

        assert "sector_detail" in viz
        assert viz["sector_detail"]["names"] == ["tech", "finance"]
        assert len(viz["sector_detail"]["allocation_effects"]) == 2

    def test_prepare_visualization_data_with_factors(self):
        """包含因子归因的可视化数据。"""
        report = _make_report()
        attr_report = self.svc.generate_attribution_report(
            report=report,
            sector_names=["tech"],
            portfolio_weights=[1.0],
            benchmark_weights=[1.0],
            portfolio_returns=[0.08],
            benchmark_returns=[0.06],
            factor_names=["market", "size"],
            portfolio_exposures=[1.1, -0.3],
            benchmark_exposures=[1.0, 0.0],
            factor_returns=[0.05, 0.02],
            benchmark_total_return=0.06,
        )

        viz = self.svc.prepare_visualization_data(attr_report)

        assert "factor_chart" in viz
        assert len(viz["factor_chart"]["categories"]) == 2
        assert "residual" in viz["factor_chart"]

    def test_summary_active_return(self):
        """可视化 summary 中超额收益正确。"""
        report = _make_report(total_return=0.08)
        attr_report = self.svc.generate_attribution_report(
            report=report,
            sector_names=["A"],
            portfolio_weights=[1.0],
            benchmark_weights=[1.0],
            portfolio_returns=[0.08],
            benchmark_returns=[0.06],
        )

        viz = self.svc.prepare_visualization_data(attr_report)
        summary = viz["summary"]

        assert abs(summary["total_return"] - 0.08) < 1e-6
        assert abs(summary["benchmark_return"] - 0.06) < 1e-6
        assert abs(summary["active_return"] - 0.02) < 1e-6
