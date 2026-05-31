"""归因分析应用服务。

编排 Brinson 归因与因子归因，从 BacktestReport 自动生成 AttributionReport。
"""
from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.backtest.services.attribution.brinson_attribution import (
    BrinsonAttributionService,
)
from src.domain.backtest.services.attribution.factor_attribution import (
    FactorAttributionService,
)
from src.domain.backtest.value_objects.attribution_report import (
    AttributionReport,
    BrinsonAttributionResult,
    FactorAttributionResult,
)


class AttributionAppService:
    """归因分析应用服务。

    协调领域服务完成归因分析，并输出统一的 AttributionReport。
    支持：
    - 基于持仓数据的 Brinson 归因
    - 基于因子数据的因子归因
    - 汇总归因结果并准备可视化数据
    """

    def __init__(
        self,
        brinson_service: BrinsonAttributionService | None = None,
        factor_service: FactorAttributionService | None = None,
    ) -> None:
        self.brinson_service = brinson_service or BrinsonAttributionService()
        self.factor_service = factor_service or FactorAttributionService()
        self._reports: list[AttributionReport] = []

    @property
    def reports(self) -> list[AttributionReport]:
        """已生成的归因报告列表。"""
        return list(self._reports)

    def run_brinson_attribution(
        self,
        strategy_name: str,
        sector_names: list[str],
        portfolio_weights: list[float],
        benchmark_weights: list[float],
        portfolio_returns: list[float],
        benchmark_returns: list[float],
    ) -> BrinsonAttributionResult:
        """执行 Brinson 归因分析。

        Args:
            strategy_name: 策略名称。
            sector_names: 行业名称列表。
            portfolio_weights: 组合各行业权重。
            benchmark_weights: 基准各行业权重。
            portfolio_returns: 组合各行业收益率。
            benchmark_returns: 基准各行业收益率。

        Returns:
            BrinsonAttributionResult 归因结果。
        """
        return self.brinson_service.analyze(
            sector_names=sector_names,
            portfolio_weights=portfolio_weights,
            benchmark_weights=benchmark_weights,
            portfolio_returns=portfolio_returns,
            benchmark_returns=benchmark_returns,
        )

    def run_factor_attribution(
        self,
        factor_names: list[str],
        portfolio_exposures: list[float],
        benchmark_exposures: list[float],
        factor_returns: list[float],
        portfolio_return: float,
        benchmark_return: float,
    ) -> FactorAttributionResult:
        """执行因子归因分析。

        Args:
            factor_names: 因子名称列表。
            portfolio_exposures: 组合因子暴露度。
            benchmark_exposures: 基准因子暴露度。
            factor_returns: 因子收益率。
            portfolio_return: 组合总收益率。
            benchmark_return: 基准总收益率。

        Returns:
            FactorAttributionResult 因子归因结果。
        """
        return self.factor_service.analyze(
            factor_names=factor_names,
            portfolio_exposures=portfolio_exposures,
            benchmark_exposures=benchmark_exposures,
            factor_returns=factor_returns,
            portfolio_return=portfolio_return,
            benchmark_return=benchmark_return,
        )

    def generate_attribution_report(
        self,
        report: BacktestReport,
        sector_names: list[str],
        portfolio_weights: list[float],
        benchmark_weights: list[float],
        portfolio_returns: list[float],
        benchmark_returns: list[float],
        factor_names: list[str] | None = None,
        portfolio_exposures: list[float] | None = None,
        benchmark_exposures: list[float] | None = None,
        factor_returns: list[float] | None = None,
        benchmark_total_return: float = 0.0,
    ) -> AttributionReport:
        """从 BacktestReport 生成完整的归因分析报告。

        自动执行 Brinson 归因，可选执行因子归因。

        Args:
            report: 回测报告。
            sector_names: 行业名称列表。
            portfolio_weights: 组合各行业权重。
            benchmark_weights: 基准各行业权重。
            portfolio_returns: 组合各行业收益率。
            benchmark_returns: 基准各行业收益率。
            factor_names: 因子名称列表（可选）。
            portfolio_exposures: 组合因子暴露度（可选）。
            benchmark_exposures: 基准因子暴露度（可选）。
            factor_returns: 因子收益率（可选）。
            benchmark_total_return: 基准总收益率。

        Returns:
            AttributionReport 归因分析综合报告。
        """
        # 1. Brinson 归因
        brinson_result = self.brinson_service.analyze(
            sector_names=sector_names,
            portfolio_weights=portfolio_weights,
            benchmark_weights=benchmark_weights,
            portfolio_returns=portfolio_returns,
            benchmark_returns=benchmark_returns,
        )

        # 2. 因子归因（可选）
        factor_result: FactorAttributionResult | None = None
        factor_contributions: dict[str, float] = {}

        if factor_names and portfolio_exposures and benchmark_exposures and factor_returns:
            factor_result = self.factor_service.analyze(
                factor_names=factor_names,
                portfolio_exposures=portfolio_exposures,
                benchmark_exposures=benchmark_exposures,
                factor_returns=factor_returns,
                portfolio_return=report.total_return,
                benchmark_return=benchmark_total_return,
            )
            factor_contributions = {
                f.factor_name: f.contribution
                for f in factor_result.factor_contributions
            }

        # 3. 构建汇总报告
        attribution_report = AttributionReport(
            strategy_name=report.strategy_name,
            generated_at=datetime.now(),
            total_return=report.total_return,
            benchmark_return=brinson_result.benchmark_return,
            allocation_effect=brinson_result.allocation_effect,
            selection_effect=brinson_result.selection_effect,
            interaction_effect=brinson_result.interaction_effect,
            factor_contributions=factor_contributions,
            brinson_detail=brinson_result,
            factor_detail=factor_result,
        )

        self._reports.append(attribution_report)
        return attribution_report

    def prepare_visualization_data(
        self, attribution_report: AttributionReport
    ) -> dict:
        """将归因报告转换为可视化所需的字典数据。

        输出格式适合前端图表库（如 ECharts）直接使用。

        Args:
            attribution_report: 归因报告。

        Returns:
            可视化数据字典，包含：
            - summary: 归因汇总数据
            - brinson_chart: Brinson 归因柱状图数据
            - factor_chart: 因子贡献图数据（如有）
        """
        result: dict = {
            "strategy_name": attribution_report.strategy_name,
            "summary": {
                "total_return": attribution_report.total_return,
                "benchmark_return": attribution_report.benchmark_return,
                "active_return": (
                    attribution_report.total_return
                    - attribution_report.benchmark_return
                ),
                "allocation_effect": attribution_report.allocation_effect,
                "selection_effect": attribution_report.selection_effect,
                "interaction_effect": attribution_report.interaction_effect,
            },
            "brinson_chart": {
                "categories": ["配置效应", "选择效应", "交互效应", "超额收益"],
                "values": [
                    attribution_report.allocation_effect,
                    attribution_report.selection_effect,
                    attribution_report.interaction_effect,
                    (attribution_report.total_return
                     - attribution_report.benchmark_return),
                ],
            },
        }

        # 行业明细
        if attribution_report.brinson_detail:
            detail = attribution_report.brinson_detail
            result["sector_detail"] = {
                "names": [s.name for s in detail.sectors],
                "allocation_effects": [
                    s.allocation_effect for s in detail.sectors
                ],
                "selection_effects": [
                    s.selection_effect for s in detail.sectors
                ],
                "interaction_effects": [
                    s.interaction_effect for s in detail.sectors
                ],
            }

        # 因子归因图
        if attribution_report.factor_contributions:
            names = list(attribution_report.factor_contributions.keys())
            values = list(attribution_report.factor_contributions.values())
            result["factor_chart"] = {
                "categories": names,
                "values": values,
            }

            # 残差
            if attribution_report.factor_detail:
                result["factor_chart"]["residual"] = (
                    attribution_report.factor_detail.residual_return
                )

        return result
