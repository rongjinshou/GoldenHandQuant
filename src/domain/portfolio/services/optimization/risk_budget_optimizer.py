"""风险预算优化器 — 纯 Python 实现。

按风险贡献分配权重，支持两种模式:
- 风险平价 (Risk Parity): 各资产对组合风险的边际贡献相等
- 风险预算 (Risk Budget): 按指定比例分配风险贡献

使用 Spinu (2013) 的凸优化公式 + 牛顿法求解，
无需 numpy/scipy。
"""

from dataclasses import dataclass

from src.domain.portfolio.value_objects.optimization_result import OptimizationResult


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskBudgetInput:
    """风险预算优化器的单个资产输入。

    Attributes:
        name: 资产名称。
        expected_return: 预期收益率（年化）。
        volatility: 波动率（年化标准差）。
        risk_budget: 风险预算比例。None 表示等风险贡献。
    """

    name: str
    expected_return: float
    volatility: float
    risk_budget: float | None = None


class RiskBudgetOptimizer:
    """风险预算组合优化器。

    实现风险平价 / 风险预算的权重分配。

    数学原理 (Spinu 2013):
      min f(w) = 0.5 * w^T Sigma w - sum(b_i * ln(w_i))
      其中 b_i 为资产 i 的风险预算

    最优条件 (KKT):
      (Sigma * w)_i = b_i / w_i  =>  w_i = b_i / (Sigma * w)_i

    使用牛顿法迭代求解。

    Args:
        assets: 资产输入列表。
        covariance_matrix: 协方差矩阵。
        max_iterations: 最大迭代次数。
        tolerance: 收敛容忍度。
    """

    def __init__(
        self,
        assets: list[RiskBudgetInput],
        covariance_matrix: list[list[float]],
        max_iterations: int = 1000,
        tolerance: float = 1e-10,
    ) -> None:
        if not assets:
            raise ValueError("assets must not be empty")
        n = len(assets)
        if len(covariance_matrix) != n:
            raise ValueError(
                f"covariance_matrix rows ({len(covariance_matrix)}) != assets count ({n})"
            )
        for i, row in enumerate(covariance_matrix):
            if len(row) != n:
                raise ValueError(
                    f"covariance_matrix row {i} length ({len(row)}) != assets count ({n})"
                )

        self._assets = assets
        self._cov = covariance_matrix
        self._n = n
        self._max_iterations = max_iterations
        self._tolerance = tolerance

    def optimize_risk_parity(self) -> OptimizationResult:
        """风险平价优化: 各资产风险贡献相等。

        Returns:
            优化结果。
        """
        budgets = [1.0 / self._n] * self._n
        return self._solve(budgets, "RiskParity")

    def optimize_risk_budget(self) -> OptimizationResult:
        """风险预算优化: 按指定预算比例分配风险。

        Returns:
            优化结果。
        """
        budgets: list[float] = []
        for a in self._assets:
            if a.risk_budget is not None:
                budgets.append(a.risk_budget)
            else:
                budgets.append(1.0 / self._n)

        # 归一化预算
        total = sum(budgets)
        if total > 0:
            budgets = [b / total for b in budgets]

        return self._solve(budgets, "RiskBudget")

    def _solve(self, budgets: list[float], name: str) -> OptimizationResult:
        """使用牛顿法求解风险预算优化。

        Spinu (2013) 公式:
          f(w) = 0.5 * w^T Sigma w - sum(b_i * ln(w_i))
          grad_f = Sigma * w - b ./ w
          hess_f = Sigma + diag(b ./ w^2)

        牛顿步: w_new = w - H^-1 * g
        使用对角近似 H^-1 避免完整矩阵求逆。

        Args:
            budgets: 归一化的风险预算。
            name: 优化器名称。

        Returns:
            优化结果。
        """
        n = self._n

        # 初始化: 反波动率加权
        w = self._initial_weights()

        for _ in range(self._max_iterations):
            # 计算 Sigma * w
            cov_w = _mat_vec(self._cov, w)

            # 梯度: g_i = (Sigma * w)_i - b_i / w_i
            grad = [cov_w[i] - budgets[i] / w[i] for i in range(n)]

            # 对角 Hessian 近似: h_i = (Sigma)_ii + b_i / w_i^2
            # 使用对角近似而非完整 Hessian，保持 O(n) 复杂度
            hess_diag = [self._cov[i][i] + budgets[i] / (w[i] * w[i]) for i in range(n)]

            # 牛顿步: w_new_i = w_i - g_i / h_i
            w_new = [w[i] - grad[i] / max(hess_diag[i], 1e-15) for i in range(n)]

            # 确保正值
            w_new = [max(wi, 1e-15) for wi in w_new]

            # 检查收敛
            diff = sum((w_new[i] - w[i]) ** 2 for i in range(n)) ** 0.5
            w = w_new
            if diff < self._tolerance:
                break

        # 归一化权重
        total = sum(w)
        w_normalized = [w[i] / total for i in range(n)]

        return self._build_result(w_normalized, name)

    def _initial_weights(self) -> list[float]:
        """初始权重: 反波动率加权。"""
        inv_vols = [1.0 / max(a.volatility, 1e-6) for a in self._assets]
        total = sum(inv_vols)
        return [iv / total for iv in inv_vols]

    def _build_result(self, w: list[float], name: str) -> OptimizationResult:
        """构建优化结果。"""
        mu = [a.expected_return for a in self._assets]
        port_ret = _dot(w, mu)
        port_var = _quad_form(w, self._cov)
        port_risk = port_var**0.5
        sharpe = port_ret / port_risk if port_risk > 1e-15 else 0.0

        weights = {self._assets[i].name: round(w[i], 8) for i in range(self._n)}

        return OptimizationResult(
            weights=weights,
            expected_return=round(port_ret, 8),
            expected_risk=round(port_risk, 8),
            sharpe_ratio=round(sharpe, 8),
            optimizer_name=name,
        )


# ── 纯 Python 线性代数工具函数 ──────────────────────────────────────


def _dot(a: list[float], b: list[float]) -> float:
    """向量点积。"""
    return sum(a[i] * b[i] for i in range(len(a)))


def _mat_vec(m: list[list[float]], v: list[float]) -> list[float]:
    """矩阵-向量乘法。"""
    return [_dot(row, v) for row in m]


def _quad_form(w: list[float], m: list[list[float]]) -> float:
    """二次型 w^T * M * w。"""
    mw = _mat_vec(m, w)
    return _dot(w, mw)
