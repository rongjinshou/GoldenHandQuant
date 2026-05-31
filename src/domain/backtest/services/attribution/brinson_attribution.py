"""Brinson-Fachler 归因分析领域服务。

采用 Brinson-Fachler 模型，将组合超额收益分解为：
- 配置效应（Allocation Effect）：因偏离基准资产配置比例带来的贡献
- 选择效应（Selection Effect）：因在各行业内选股能力带来的贡献
- 交互效应（Interaction Effect）：配置与选择的交叉项

公式（对每个行业 i）：
- 配置效应 = (Wp_i - Wb_i) * Rb_i
- 选择效应 = Wb_i * (Rp_i - Rb_i)
- 交互效应 = (Wp_i - Wb_i) * (Rp_i - Rb_i)
- 行业总贡献 = 配置 + 选择 + 交互

其中 Wp_i = 组合中行业 i 权重，Wb_i = 基准中行业 i 权重，
      Rp_i = 组合中行业 i 收益率，Rb_i = 基准中行业 i 收益率。
"""

from src.domain.backtest.value_objects.attribution_report import (
    BrinsonAttributionResult,
    SectorAttributionRow,
)


class BrinsonAttributionService:
    """Brinson 归因分析领域服务。

    纯 Python 实现，不依赖任何第三方库。
    """

    def analyze(
        self,
        sector_names: list[str],
        portfolio_weights: list[float],
        benchmark_weights: list[float],
        portfolio_returns: list[float],
        benchmark_returns: list[float],
    ) -> BrinsonAttributionResult:
        """执行 Brinson 归因分析。

        Args:
            sector_names: 行业/资产类别名称列表。
            portfolio_weights: 组合中各行业权重（应归一化为 1.0）。
            benchmark_weights: 基准中各行业权重（应归一化为 1.0）。
            portfolio_returns: 组合中各行业收益率。
            benchmark_returns: 基准中各行业收益率。

        Returns:
            BrinsonAttributionResult 归因分析结果。

        Raises:
            ValueError: 输入列表长度不一致。
        """
        n = len(sector_names)
        if not (len(portfolio_weights) == len(benchmark_weights)
                == len(portfolio_returns) == len(benchmark_returns) == n):
            raise ValueError(
                f"Input lists must have the same length. "
                f"Got: names={len(sector_names)}, pw={len(portfolio_weights)}, "
                f"bw={len(benchmark_weights)}, pr={len(portfolio_returns)}, "
                f"br={len(benchmark_returns)}"
            )

        sectors: list[SectorAttributionRow] = []
        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0

        for i in range(n):
            wp = portfolio_weights[i]
            wb = benchmark_weights[i]
            rp = portfolio_returns[i]
            rb = benchmark_returns[i]

            allocation = (wp - wb) * rb
            selection = wb * (rp - rb)
            interaction = (wp - wb) * (rp - rb)

            sectors.append(SectorAttributionRow(
                name=sector_names[i],
                portfolio_weight=wp,
                benchmark_weight=wb,
                portfolio_return=rp,
                benchmark_return=rb,
                allocation_effect=round(allocation, 8),
                selection_effect=round(selection, 8),
                interaction_effect=round(interaction, 8),
            ))

            total_allocation += allocation
            total_selection += selection
            total_interaction += interaction

        total_return = sum(wp * rp for wp, rp in zip(portfolio_weights, portfolio_returns))
        benchmark_return = sum(wb * rb for wb, rb in zip(benchmark_weights, benchmark_returns))

        return BrinsonAttributionResult(
            total_return=round(total_return, 8),
            benchmark_return=round(benchmark_return, 8),
            active_return=round(total_return - benchmark_return, 8),
            allocation_effect=round(total_allocation, 8),
            selection_effect=round(total_selection, 8),
            interaction_effect=round(total_interaction, 8),
            sectors=sectors,
        )
