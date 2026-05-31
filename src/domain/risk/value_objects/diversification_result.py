from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class DiversificationResult:
    """组合分散度评估结果。

    Attributes:
        diversification_ratio: 分散比率 = 组合波动率 / 加权平均波动率。值越大分散效果越好。
        effective_strategies: 有效策略数（基于权重集中度的 Herfindahl 指数）。
        concentration_index: 权重集中度（HHI，0-1，越低越分散）。
        max_pairwise_correlation: 最高策略对相关系数。
        is_well_diversified: 是否充分分散（分散比率 > 1.2 且 HHI < 0.25）。
    """

    diversification_ratio: float
    effective_strategies: float
    concentration_index: float
    max_pairwise_correlation: float
    is_well_diversified: bool
