from src.domain.risk.value_objects.correlation_matrix import CorrelationMatrix
from src.domain.risk.value_objects.diversification_result import DiversificationResult


class DiversificationEvaluator:
    """分散度评估器。"""

    def evaluate(
        self,
        weights: dict[str, float],
        volatilities: dict[str, float],
        correlation: CorrelationMatrix,
    ) -> DiversificationResult:
        """评估组合的分散程度。

        Args:
            weights: {strategy_name: weight}，权重之和应为 1.0。
            volatilities: {strategy_name: annualized_volatility}。
            correlation: 策略间相关性矩阵。

        Returns:
            DiversificationResult: 分散度评估结果。
        """
        names = correlation.strategy_names
        n = len(names)

        w = [weights.get(name, 0.0) for name in names]
        sigma = [volatilities.get(name, 0.0) for name in names]

        # HHI = sum(wi^2)
        hhi = sum(wi**2 for wi in w)
        n_eff = 1.0 / hhi if hhi > 0 else 0.0

        # 组合波动率: sigma_p = sqrt(w^T * Sigma * w)
        # Sigma[i][j] = rho[i][j] * sigma_i * sigma_j
        portfolio_var = 0.0
        for i in range(n):
            for j in range(n):
                portfolio_var += w[i] * w[j] * correlation.matrix[i][j] * sigma[i] * sigma[j]
        sigma_p = portfolio_var**0.5 if portfolio_var > 0 else 0.0

        # 加权平均波动率
        weighted_avg_vol = sum(wi * si for wi, si in zip(w, sigma))

        # 分散比率
        dr = weighted_avg_vol / sigma_p if sigma_p > 0 else 1.0

        # 最高策略对相关系数
        max_corr = correlation.max_correlation_pair[2] if n >= 2 else 0.0

        # 充分分散: DR > 1.2 且 HHI < 0.25
        is_well_diversified = dr > 1.2 and hhi < 0.25

        return DiversificationResult(
            diversification_ratio=dr,
            effective_strategies=n_eff,
            concentration_index=hhi,
            max_pairwise_correlation=max_corr,
            is_well_diversified=is_well_diversified,
        )
