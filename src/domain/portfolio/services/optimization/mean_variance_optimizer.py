"""均值-方差优化器 — 纯 Python 实现。

使用投影梯度下降求解 Markowitz 均值-方差优化问题，
支持最大夏普比率和最小方差两种目标，以及权重上下限和行业限制约束。
"""

from dataclasses import dataclass

from src.domain.portfolio.value_objects.optimization_result import OptimizationResult


@dataclass(frozen=True, slots=True, kw_only=True)
class AssetInput:
    """优化器的单个资产输入。

    Attributes:
        name: 资产名称。
        expected_return: 预期收益率（年化）。
        volatility: 波动率（年化标准差）。
    """

    name: str
    expected_return: float
    volatility: float


@dataclass(frozen=True, slots=True, kw_only=True)
class MeanVarianceConfig:
    """均值-方差优化配置。

    Attributes:
        risk_free_rate: 无风险利率。
        min_weight: 单资产权重下限。
        max_weight: 单资产权重上限。
        max_iterations: 梯度下降最大迭代次数。
        learning_rate: 学习率。
        tolerance: 收敛容忍度。
    """

    risk_free_rate: float = 0.03
    min_weight: float = 0.0
    max_weight: float = 1.0
    max_iterations: int = 5000
    learning_rate: float = 0.01
    tolerance: float = 1e-8


@dataclass(frozen=True, slots=True, kw_only=True)
class IndustryConstraint:
    """行业约束。

    Attributes:
        industry_name: 行业名称。
        asset_names: 属于该行业的资产名称列表。
        max_weight: 该行业的权重上限。
    """

    industry_name: str
    asset_names: list[str]
    max_weight: float


class MeanVarianceOptimizer:
    """均值-方差组合优化器。

    实现 Markowitz 均值-方差框架的两种经典优化:
    - 最大夏普比率: max (w^T * mu - rf) / sqrt(w^T * Sigma * w)
    - 最小方差: min w^T * Sigma * w

    使用纯 Python 实现的投影梯度下降算法，不依赖 numpy/scipy。

    约束条件:
    - 权重上下限 (box constraints)
    - 权重之和 = 1
    - 行业集中度限制

    Args:
        assets: 资产列表。
        covariance_matrix: 协方差矩阵（n x n），按 assets 顺序排列。
        config: 优化配置。
        industry_constraints: 行业约束列表。
    """

    def __init__(
        self,
        assets: list[AssetInput],
        covariance_matrix: list[list[float]],
        config: MeanVarianceConfig | None = None,
        industry_constraints: list[IndustryConstraint] | None = None,
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
        self._config = config or MeanVarianceConfig()
        self._industry_constraints = industry_constraints or []
        self._n = n

    def optimize_max_sharpe(self) -> OptimizationResult:
        """最大夏普比率优化。

        通过投影梯度下降最大化夏普比率:
        SR = (w^T * mu - rf) / sqrt(w^T * Sigma * w)

        实际使用最小化负夏普比率的等价形式。

        Returns:
            优化结果。
        """
        if self._n == 1:
            return self._single_asset_result()

        # 初始化为等权
        w = [1.0 / self._n] * self._n
        cfg = self._config
        mu = [a.expected_return for a in self._assets]
        rf = cfg.risk_free_rate

        for _ in range(cfg.max_iterations):
            # 计算组合收益和风险
            port_ret = _dot(w, mu)
            port_var = _quad_form(w, self._cov)
            port_risk = port_var**0.5

            if port_risk < 1e-15:
                break

            # 负夏普比率对 w 的梯度
            # d(-SR)/dw = -(mu - rf) * risk + (ret - rf) * (Sigma * w) / risk
            #            -----------------------------------------------
            #                              risk^2
            excess_ret = port_ret - rf
            cov_w = _mat_vec(self._cov, w)
            grad: list[float] = []
            for i in range(self._n):
                g = -(mu[i] - rf) * port_risk + excess_ret * cov_w[i] / port_risk
                g /= port_risk * port_risk
                grad.append(g)

            # 梯度下降
            w_new = [w[i] - cfg.learning_rate * grad[i] for i in range(self._n)]

            # 投影到可行域
            w_new = self._project(w_new)

            # 检查收敛
            diff = sum((w_new[i] - w[i]) ** 2 for i in range(self._n)) ** 0.5
            w = w_new
            if diff < cfg.tolerance:
                break

        return self._build_result(w, "MeanVariance_MaxSharpe")

    def optimize_min_variance(self) -> OptimizationResult:
        """最小方差优化。

        通过投影梯度下降最小化组合方差:
        min w^T * Sigma * w
        s.t. sum(w) = 1, w_lo <= w <= w_hi

        Returns:
            优化结果。
        """
        if self._n == 1:
            return self._single_asset_result()

        w = [1.0 / self._n] * self._n
        cfg = self._config

        for _ in range(cfg.max_iterations):
            # 梯度: d(w^T Sigma w)/dw = 2 * Sigma * w
            cov_w = _mat_vec(self._cov, w)
            grad = [2.0 * cov_w[i] for i in range(self._n)]

            w_new = [w[i] - cfg.learning_rate * grad[i] for i in range(self._n)]
            w_new = self._project(w_new)

            diff = sum((w_new[i] - w[i]) ** 2 for i in range(self._n)) ** 0.5
            w = w_new
            if diff < cfg.tolerance:
                break

        return self._build_result(w, "MeanVariance_MinVariance")

    def _project(self, w: list[float]) -> list[float]:
        """将权重投影到可行域: box constraints + 行业约束 + 归一化。

        使用交替投影法:
        1. 投影到 box constraints [min_weight, max_weight]
        2. 投影到行业约束
        3. 归一化使权重之和 = 1

        Args:
            w: 原始权重。

        Returns:
            投影后的权重。
        """
        cfg = self._config

        # 1. Box constraints
        w = [max(cfg.min_weight, min(cfg.max_weight, w[i])) for i in range(self._n)]

        # 2. 行业约束
        for ic in self._industry_constraints:
            indices = [
                i for i, a in enumerate(self._assets) if a.name in ic.asset_names
            ]
            if not indices:
                continue
            industry_sum = sum(w[i] for i in indices)
            if industry_sum > ic.max_weight and industry_sum > 0:
                scale = ic.max_weight / industry_sum
                for i in indices:
                    w[i] *= scale

        # 3. 归一化
        total = sum(w)
        if total > 0:
            w = [w[i] / total for i in range(self._n)]

        return w

    def _build_result(self, w: list[float], name: str) -> OptimizationResult:
        """构建优化结果。"""
        mu = [a.expected_return for a in self._assets]
        port_ret = _dot(w, mu)
        port_var = _quad_form(w, self._cov)
        port_risk = port_var**0.5
        rf = self._config.risk_free_rate
        sharpe = (port_ret - rf) / port_risk if port_risk > 1e-15 else 0.0

        weights = {self._assets[i].name: round(w[i], 8) for i in range(self._n)}

        return OptimizationResult(
            weights=weights,
            expected_return=round(port_ret, 8),
            expected_risk=round(port_risk, 8),
            sharpe_ratio=round(sharpe, 8),
            optimizer_name=name,
        )

    def _single_asset_result(self) -> OptimizationResult:
        """单资产直接返回 100% 权重。"""
        a = self._assets[0]
        rf = self._config.risk_free_rate
        sharpe = (a.expected_return - rf) / a.volatility if a.volatility > 1e-15 else 0.0
        return OptimizationResult(
            weights={a.name: 1.0},
            expected_return=a.expected_return,
            expected_risk=a.volatility,
            sharpe_ratio=round(sharpe, 8),
            optimizer_name="MeanVariance_SingleAsset",
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
