"""Black-Litterman 模型优化器 — 纯 Python 实现。

将市场均衡收益与投资者主观观点结合，生成后验收益估计，
再输入均值-方差框架进行优化。

数学公式:
  后验精度 = 先验精度 + 观点精度  (tau * Sigma)^-1 + P^T * Omega^-1 * P
  后验均值 = 后验精度^-1 * [(tau * Sigma)^-1 * Pi + P^T * Omega^-1 * Q]

其中:
  Pi = 市场均衡收益（反向优化推导）
  P = 观点矩阵
  Q = 观点收益向量
  Omega = 观点不确定性矩阵
  tau = 标量缩放因子（通常取 0.025 ~ 0.05）
"""

from dataclasses import dataclass

from src.domain.portfolio.services.optimization.mean_variance_optimizer import (
    AssetInput,
    MeanVarianceConfig,
    MeanVarianceOptimizer,
)
from src.domain.portfolio.value_objects.optimization_result import OptimizationResult


@dataclass(frozen=True, slots=True, kw_only=True)
class InvestorView:
    """投资者观点。

    表达为资产收益的线性组合: P * r = Q + epsilon。

    Attributes:
        asset_weights: 观点涉及的资产及其系数 {asset_name: coefficient}。
        expected_return: 观点预期收益 Q。
        confidence: 观点置信度 (0, 1]，1 表示完全确信。
    """

    asset_weights: dict[str, float]
    expected_return: float
    confidence: float

    def __post_init__(self) -> None:
        if not (0.0 < self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be in (0, 1], got {self.confidence}"
            )


class BlackLittermanOptimizer:
    """Black-Litterman 组合优化器。

    实现步骤:
    1. 从市场权重反推均衡收益 (reverse optimization)
    2. 结合投资者观点生成后验收益
    3. 使用后验收益进行均值-方差优化

    Args:
        asset_names: 资产名称列表。
        market_weights: 市场均衡权重。
        covariance_matrix: 协方差矩阵。
        risk_aversion: 风险厌恶系数 (delta)。
        tau: 不确定性缩放因子。
        views: 投资者观点列表。
        config: 均值-方差优化配置。
    """

    def __init__(
        self,
        asset_names: list[str],
        market_weights: list[float],
        covariance_matrix: list[list[float]],
        risk_aversion: float = 2.5,
        tau: float = 0.05,
        views: list[InvestorView] | None = None,
        config: MeanVarianceConfig | None = None,
    ) -> None:
        n = len(asset_names)
        if n == 0:
            raise ValueError("asset_names must not be empty")
        if len(market_weights) != n:
            raise ValueError(
                f"market_weights length ({len(market_weights)}) != asset count ({n})"
            )
        if len(covariance_matrix) != n:
            raise ValueError(
                f"covariance_matrix rows ({len(covariance_matrix)}) != asset count ({n})"
            )
        for i, row in enumerate(covariance_matrix):
            if len(row) != n:
                raise ValueError(
                    f"covariance_matrix row {i} length ({len(row)}) != asset count ({n})"
                )

        self._asset_names = asset_names
        self._market_weights = market_weights
        self._cov = covariance_matrix
        self._delta = risk_aversion
        self._tau = tau
        self._views = views or []
        self._config = config or MeanVarianceConfig()
        self._n = n

    def optimize(self) -> OptimizationResult:
        """执行 Black-Litterman 优化。

        Returns:
            优化结果。
        """
        # Step 1: 反向优化推导均衡收益 Pi = delta * Sigma * w_mkt
        cov_w = _mat_vec(self._cov, self._market_weights)
        pi = [self._delta * cov_w[i] for i in range(self._n)]

        if not self._views:
            # 无观点时直接用均衡收益做均值-方差优化
            return self._optimize_with_returns(pi, "BlackLitterman_Equilibrium")

        # Step 2: 构建观点矩阵 P, Q, Omega
        k = len(self._views)
        p_matrix = [[0.0] * self._n for _ in range(k)]
        q_vector: list[float] = []
        omega_diag: list[float] = []

        for j, view in enumerate(self._views):
            q_vector.append(view.expected_return)
            for i, name in enumerate(self._asset_names):
                p_matrix[j][i] = view.asset_weights.get(name, 0.0)
            # Omega_jj = (1/confidence - 1) * P_j * (tau * Sigma) * P_j^T
            # 经典 Black-Litterman: Omega = diag(P * (tau*Sigma) * P^T) / confidence_scale
            p_row = p_matrix[j]
            tau_cov_p = _mat_vec_scaled(self._cov, p_row, self._tau)
            p_tau_cov_p = _dot(p_row, tau_cov_p)
            # 使用 (1/confidence - 1) 缩放
            scale = (1.0 / view.confidence - 1.0) if view.confidence < 1.0 else 0.001
            omega_diag.append(scale * p_tau_cov_p + 1e-10)

        # Step 3: 后验收益计算
        # posterior_precision = (tau * Sigma)^-1 + P^T * Omega^-1 * P
        # posterior_mean = posterior_precision^-1 * [(tau*Sigma)^-1 * Pi + P^T * Omega^-1 * Q]
        # 使用简化的逐元素近似（对角近似）避免完整矩阵求逆

        # (tau * Sigma)^-1 * Pi ≈ Pi / tau (对角近似下)
        # 实际: 使用迭代方法计算后验均值
        posterior_returns = self._compute_posterior(pi, p_matrix, q_vector, omega_diag)

        return self._optimize_with_returns(posterior_returns, "BlackLitterman")

    def _compute_posterior(
        self,
        pi: list[float],
        p_matrix: list[list[float]],
        q_vector: list[float],
        omega_diag: list[float],
    ) -> list[float]:
        """计算后验收益（使用对角近似的解析解）。

        对角近似: 假设协方差矩阵和后验精度矩阵均为对角矩阵，
        从而避免完整的矩阵求逆运算。

        Args:
            pi: 均衡收益。
            p_matrix: 观点矩阵 (k x n)。
            q_vector: 观点收益向量 (k)。
            omega_diag: 观点不确定性对角元素 (k)。

        Returns:
            后验收益向量 (n)。
        """
        tau = self._tau
        n = self._n
        k = len(q_vector)

        # 先验精度（对角近似）: 1 / (tau * sigma_ii)
        prior_precision: list[float] = []
        for i in range(n):
            var_i = self._cov[i][i] * tau
            prior_precision.append(1.0 / max(var_i, 1e-15))

        # P^T * Omega^-1 * P 的对角贡献
        pt_omega_inv_p_diag = [0.0] * n
        # P^T * Omega^-1 * Q
        pt_omega_inv_q = [0.0] * n

        for j in range(k):
            omega_inv_j = 1.0 / max(omega_diag[j], 1e-15)
            for i in range(n):
                p_ji = p_matrix[j][i]
                pt_omega_inv_p_diag[i] += p_ji * p_ji * omega_inv_j
                pt_omega_inv_q[i] += p_ji * omega_inv_j * q_vector[j]

        # 后验均值
        posterior: list[float] = []
        for i in range(n):
            post_precision_i = prior_precision[i] + pt_omega_inv_p_diag[i]
            prior_contrib = prior_precision[i] * pi[i]
            post_mean_i = (prior_contrib + pt_omega_inv_q[i]) / max(post_precision_i, 1e-15)
            posterior.append(post_mean_i)

        return posterior

    def _optimize_with_returns(
        self, expected_returns: list[float], name: str
    ) -> OptimizationResult:
        """使用给定的预期收益进行均值-方差优化。"""
        assets = [
            AssetInput(
                name=self._asset_names[i],
                expected_return=expected_returns[i],
                volatility=self._cov[i][i] ** 0.5,
            )
            for i in range(self._n)
        ]
        optimizer = MeanVarianceOptimizer(
            assets=assets,
            covariance_matrix=self._cov,
            config=self._config,
        )
        result = optimizer.optimize_max_sharpe()
        return OptimizationResult(
            weights=result.weights,
            expected_return=result.expected_return,
            expected_risk=result.expected_risk,
            sharpe_ratio=result.sharpe_ratio,
            optimizer_name=name,
        )


# ── 纯 Python 线性代数工具函数 ──────────────────────────────────────


def _dot(a: list[float], b: list[float]) -> float:
    """向量点积。"""
    return sum(a[i] * b[i] for i in range(len(a)))


def _mat_vec(m: list[list[float]], v: list[float]) -> list[float]:
    """矩阵-向量乘法。"""
    return [_dot(row, v) for row in m]


def _mat_vec_scaled(m: list[list[float]], v: list[float], scale: float) -> list[float]:
    """scale * (M * v)。"""
    return [scale * _dot(row, v) for row in m]
