"""因子归因分析领域服务。

将组合收益按风格因子进行分解，分析各因子的暴露度及其对收益的贡献。

支持的因子包括（可扩展）：
- market（市场因子）：组合 beta 暴露
- size（规模因子）：大/小盘暴露
- value（价值因子）：价值/成长暴露
- momentum（动量因子）：动量暴露

因子归因模型：
- 超额收益 = sum(因子暴露差 * 因子收益) + 残差
- 因子暴露通过组合持仓加权计算
"""

from src.domain.backtest.value_objects.attribution_report import (
    FactorAttributionResult,
    FactorExposure,
)


class FactorAttributionService:
    """因子归因分析领域服务。

    纯 Python 实现，不依赖任何第三方库。

    使用方法：通过 analyze() 传入各因子的组合暴露、基准暴露和因子收益，
    计算各因子对超额收益的贡献以及残差。
    """

    def analyze(
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
            portfolio_exposures: 组合对各因子的暴露度。
            benchmark_exposures: 基准对各因子的暴露度。
            factor_returns: 各因子本期收益率。
            portfolio_return: 组合总收益率。
            benchmark_return: 基准总收益率。

        Returns:
            FactorAttributionResult 因子归因结果。

        Raises:
            ValueError: 输入列表长度不一致。
        """
        n = len(factor_names)
        if not (len(portfolio_exposures) == len(benchmark_exposures)
                == len(factor_returns) == n):
            raise ValueError(
                f"Input lists must have the same length. "
                f"Got: names={len(factor_names)}, pe={len(portfolio_exposures)}, "
                f"be={len(benchmark_exposures)}, fr={len(factor_returns)}"
            )

        factors: list[FactorExposure] = []
        explained_active = 0.0

        for i in range(n):
            spread = portfolio_exposures[i] - benchmark_exposures[i]
            contribution = spread * factor_returns[i]

            factors.append(FactorExposure(
                factor_name=factor_names[i],
                portfolio_exposure=portfolio_exposures[i],
                benchmark_exposure=benchmark_exposures[i],
                factor_spread=round(spread, 8),
                factor_return=factor_returns[i],
                contribution=round(contribution, 8),
            ))

            explained_active += contribution

        active_return = portfolio_return - benchmark_return
        residual = active_return - explained_active

        return FactorAttributionResult(
            total_return=portfolio_return,
            benchmark_return=benchmark_return,
            active_return=round(active_return, 8),
            factor_contributions=factors,
            residual_return=round(residual, 8),
        )
