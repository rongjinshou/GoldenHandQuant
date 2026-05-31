"""归因分析报告值对象。

包含 Brinson 归因和因子归因的结果数据结构。
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class SectorAttributionRow:
    """单行业/资产类的 Brinson 归因明细行。

    Attributes:
        name: 行业或资产类别名称。
        portfolio_weight: 组合中该行业的权重。
        benchmark_weight: 基准中该行业的权重。
        portfolio_return: 组合中该行业的收益率。
        benchmark_return: 基准中该行业的收益率。
        allocation_effect: 配置效应 = (wp - wb) * Rb。
        selection_effect: 选择效应 = wb * (Rp - Rb)。
        interaction_effect: 交互效应 = (wp - wb) * (Rp - Rb)。
    """
    name: str
    portfolio_weight: float
    benchmark_weight: float
    portfolio_return: float
    benchmark_return: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float


@dataclass(frozen=True, slots=True, kw_only=True)
class BrinsonAttributionResult:
    """Brinson 归因分析结果。

    采用 Brinson-Fachler 模型，将组合超额收益分解为：
    - 配置效应（Allocation Effect）：资产配置偏离基准带来的贡献
    - 选择效应（Selection Effect）：个股选择偏离基准带来的贡献
    - 交互效应（Interaction Effect）：配置与选择的交叉贡献

    Attributes:
        total_return: 组合总收益率。
        benchmark_return: 基准总收益率。
        active_return: 超额收益 = total_return - benchmark_return。
        allocation_effect: 配置效应合计。
        selection_effect: 选择效应合计。
        interaction_effect: 交互效应合计。
        sectors: 各行业/资产类别的归因明细。
    """
    total_return: float
    benchmark_return: float
    active_return: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    sectors: list[SectorAttributionRow] = field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorExposure:
    """单因子暴露度。

    Attributes:
        factor_name: 因子名称（如 market, size, value, momentum 等）。
        portfolio_exposure: 组合对该因子的暴露度。
        benchmark_exposure: 基准对该因子的暴露度。
        factor_spread: 因子利差 = portfolio_exposure - benchmark_exposure。
        factor_return: 该因子本期收益率。
        contribution: 该因子对超额收益的贡献 = factor_spread * factor_return。
    """
    factor_name: str
    portfolio_exposure: float
    benchmark_exposure: float
    factor_spread: float
    factor_return: float
    contribution: float


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorAttributionResult:
    """因子归因分析结果。

    将组合收益按风格因子（市场、规模、价值、动量等）进行分解，
    分析各因子的暴露度及其对收益的贡献。

    Attributes:
        total_return: 组合总收益率。
        benchmark_return: 基准总收益率。
        active_return: 超额收益。
        factor_contributions: 各因子的暴露度与贡献明细。
        residual_return: 残差收益（未被因子解释的部分）。
    """
    total_return: float
    benchmark_return: float
    active_return: float
    factor_contributions: list[FactorExposure] = field(default_factory=list)
    residual_return: float = 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributionReport:
    """归因分析综合报告值对象。

    聚合 Brinson 归因与因子归因，用于回测结果的深度分析。

    Attributes:
        strategy_name: 策略名称。
        generated_at: 报告生成时间。
        total_return: 组合总收益率。
        benchmark_return: 基准总收益率。
        allocation_effect: 配置效应合计。
        selection_effect: 选择效应合计。
        interaction_effect: 交互效应合计。
        factor_contributions: 各因子贡献明细（因子名 -> 贡献值）。
        brinson_detail: Brinson 归因详细结果。
        factor_detail: 因子归因详细结果。
    """
    strategy_name: str
    generated_at: datetime
    total_return: float
    benchmark_return: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    factor_contributions: dict[str, float] = field(default_factory=dict)
    brinson_detail: BrinsonAttributionResult | None = None
    factor_detail: FactorAttributionResult | None = None
