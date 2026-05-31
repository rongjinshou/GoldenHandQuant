"""因子研发流水线领域服务。

负责:
- 因子生命周期管理 (DISCOVERED → TESTING → VALIDATED → ACTIVE → DECAYED → RETIRED)
- 因子衰减监控 + 自动淘汰
- 因子组合优化 (正交化、逐步回归)

Domain 层仅使用标准库。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.strategy.factor_test.report import FactorTestReport
from src.domain.strategy.factor_test.scorer import FactorScorer
from src.domain.strategy.value_objects.factor_lifecycle_status import FactorLifecycleStatus

# ---------------------------------------------------------------------------
# 合法状态转换
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[FactorLifecycleStatus, set[FactorLifecycleStatus]] = {
    FactorLifecycleStatus.DISCOVERED: {
        FactorLifecycleStatus.TESTING,
        FactorLifecycleStatus.RETIRED,
    },
    FactorLifecycleStatus.TESTING: {
        FactorLifecycleStatus.VALIDATED,
        FactorLifecycleStatus.DISCOVERED,  # 检验不通过回退
        FactorLifecycleStatus.RETIRED,
    },
    FactorLifecycleStatus.VALIDATED: {
        FactorLifecycleStatus.ACTIVE,
        FactorLifecycleStatus.RETIRED,
    },
    FactorLifecycleStatus.ACTIVE: {
        FactorLifecycleStatus.DECAYED,
        FactorLifecycleStatus.RETIRED,
    },
    FactorLifecycleStatus.DECAYED: {
        FactorLifecycleStatus.TESTING,  # 重新验证
        FactorLifecycleStatus.RETIRED,
    },
    FactorLifecycleStatus.RETIRED: set(),  # 终态
}


# ---------------------------------------------------------------------------
# 因子生命周期条目 (实体)
# ---------------------------------------------------------------------------

@dataclass(slots=True, kw_only=True)
class FactorLifecycleEntry:
    """因子生命周期条目。"""

    factor_name: str
    expression: str
    status: FactorLifecycleStatus = FactorLifecycleStatus.DISCOVERED
    score: float = 0.0
    grade: str = ""
    ic_mean: float = 0.0
    ir: float = 0.0
    validation_ic: float = 0.0   # VALIDATED 阶段的 IC 基准值，用于衰减判断
    decay_count: int = 0         # 连续衰减计数
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    reason: str = ""

    def transition_to(self, target: FactorLifecycleStatus, reason: str = "") -> None:
        """执行状态转换，非法转换抛 ValueError。"""
        allowed = _VALID_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise ValueError(
                f"Invalid factor lifecycle transition: {self.status} -> {target} "
                f"(allowed: {allowed or 'none'})"
            )
        self.status = target
        self.updated_at = datetime.now()
        if reason:
            self.reason = reason

    def update_metrics(
        self,
        score: float,
        grade: str,
        ic_mean: float,
        ir: float,
    ) -> None:
        """更新因子检验指标。"""
        self.score = score
        self.grade = grade
        self.ic_mean = ic_mean
        self.ir = ir
        self.updated_at = datetime.now()


# ---------------------------------------------------------------------------
# 因子衰减监控
# ---------------------------------------------------------------------------

# 衰减阈值: IC 降至验证期 IC 的此比例以下视为衰减
_DEFAULT_DECAY_IC_RATIO: float = 0.5
# 连续衰减次数达到此阈值自动退役
_DEFAULT_DECAY_RETIRE_COUNT: int = 3


@dataclass(frozen=True, slots=True, kw_only=True)
class DecayCheckResult:
    """衰减检查结果。"""

    factor_name: str
    is_decayed: bool
    current_ic: float
    validation_ic: float
    ic_ratio: float
    decay_count: int


class FactorDecayMonitor:
    """因子衰减监控器 (领域服务)。

    检查 ACTIVE 因子的近期 IC 是否相对于验证期 IC 显著下降。
    """

    def __init__(
        self,
        decay_ic_ratio: float = _DEFAULT_DECAY_IC_RATIO,
        retire_after: int = _DEFAULT_DECAY_RETIRE_COUNT,
    ) -> None:
        self._decay_ic_ratio = decay_ic_ratio
        self._retire_after = retire_after

    def check_decay(
        self,
        entry: FactorLifecycleEntry,
        current_ic_mean: float,
    ) -> DecayCheckResult:
        """检查单个因子是否衰减。

        Args:
            entry: 因子生命周期条目。
            current_ic_mean: 最近一个检查周期的 IC 均值。

        Returns:
            DecayCheckResult。
        """
        validation_ic = entry.validation_ic
        if validation_ic == 0:
            ic_ratio = 0.0
        else:
            ic_ratio = abs(current_ic_mean) / abs(validation_ic)

        is_decayed = ic_ratio < self._decay_ic_ratio

        return DecayCheckResult(
            factor_name=entry.factor_name,
            is_decayed=is_decayed,
            current_ic=current_ic_mean,
            validation_ic=validation_ic,
            ic_ratio=ic_ratio,
            decay_count=entry.decay_count + (1 if is_decayed else 0),
        )

    def should_retire(self, entry: FactorLifecycleEntry) -> bool:
        """判断因子是否应自动退役（连续衰减次数达标）。"""
        return entry.decay_count >= self._retire_after


# ---------------------------------------------------------------------------
# 因子组合优化
# ---------------------------------------------------------------------------

class FactorCombiner:
    """因子组合优化 (领域服务)。

    提供正交化 (Gram-Schmidt) 和逐步回归两种因子选择/组合方法。
    仅使用标准库，不依赖 numpy/pandas。
    """

    @staticmethod
    def orthogonalize(
        factor_matrix: list[list[float]],
    ) -> list[list[float]]:
        """Gram-Schmidt 正交化。

        将因子矩阵正交化，消除因子间的共线性。

        Args:
            factor_matrix: shape (n_samples, n_factors) 的因子值矩阵。
                每行是一个样本，每列是一个因子。

        Returns:
            正交化后的因子矩阵，shape (n_samples, n_factors)。
        """
        if not factor_matrix or not factor_matrix[0]:
            return []

        n_samples = len(factor_matrix)
        n_factors = len(factor_matrix[0])

        # 转置为列向量操作更方便: columns[j] = 第 j 个因子的所有样本值
        columns: list[list[float]] = [
            [factor_matrix[i][j] for i in range(n_samples)]
            for j in range(n_factors)
        ]

        ortho_columns: list[list[float]] = []

        for j in range(n_factors):
            v = list(columns[j])
            # 减去在已正交化方向上的投影
            for k in range(len(ortho_columns)):
                u = ortho_columns[k]
                dot_vu = sum(v[i] * u[i] for i in range(n_samples))
                dot_uu = sum(u[i] * u[i] for i in range(n_samples))
                if dot_uu == 0:
                    continue
                proj = dot_vu / dot_uu
                v = [v[i] - proj * u[i] for i in range(n_samples)]
            ortho_columns.append(v)

        # 转置回行优先
        result = [
            [ortho_columns[j][i] for j in range(n_factors)]
            for i in range(n_samples)
        ]
        return result

    @staticmethod
    def stepwise_select(
        factor_values: list[dict[str, float]],
        target_values: list[float],
        factor_names: list[str],
        max_factors: int | None = None,
        min_improvement: float = 1e-4,
    ) -> list[str]:
        """逐步回归选择因子 (前向选择)。

        基于与目标值的相关性逐步加入因子，直到增益不足。

        Args:
            factor_values: 每个样本的因子值字典列表。
            target_values: 目标值列表（如未来收益）。
            factor_names: 候选因子名列表。
            max_factors: 最大因子数，None 表示不限。
            min_improvement: 最小 R² 改善阈值。

        Returns:
            被选中的因子名列表（按选择顺序）。
        """
        n = len(target_values)
        if n == 0 or not factor_names:
            return []

        selected: list[str] = []
        remaining = set(factor_names)
        best_r2 = 0.0
        limit = max_factors or len(factor_names)

        for _ in range(limit):
            if not remaining:
                break

            best_candidate: str | None = None
            best_candidate_r2 = best_r2

            for name in remaining:
                trial = selected + [name]
                r2 = _compute_r2(factor_values, target_values, trial, n)
                if r2 > best_candidate_r2:
                    best_candidate_r2 = r2
                    best_candidate = name

            if best_candidate is None:
                break
            improvement = best_candidate_r2 - best_r2
            if improvement < min_improvement:
                break

            selected.append(best_candidate)
            remaining.discard(best_candidate)
            best_r2 = best_candidate_r2

        return selected


def _compute_r2(
    factor_values: list[dict[str, float]],
    target: list[float],
    selected_names: list[str],
    n: int,
) -> float:
    """计算多元线性回归的 R²（使用正规方程的简化实现）。

    仅使用标准库。
    """
    if not selected_names or n == 0:
        return 0.0

    # 构建设计矩阵 X: 每行 [1, factor1, factor2, ...]
    p = len(selected_names)
    X: list[list[float]] = []
    y: list[float] = []
    for i in range(n):
        row = [1.0]  # 截距
        skip = False
        for name in selected_names:
            val = factor_values[i].get(name)
            if val is None:
                skip = True
                break
            row.append(val)
        if skip:
            continue
        X.append(row)
        y.append(target[i])

    actual_n = len(X)
    if actual_n <= p + 1:
        return 0.0

    # 正规方程: beta = (X^T X)^{-1} X^T y
    # 使用高斯消元求解
    XtX = _mat_mul_transpose_first(X, X)
    Xty = _mat_vec_mul_transpose(X, y)

    beta = _solve_linear_system(XtX, Xty)
    if beta is None:
        return 0.0

    # 计算 R²
    y_mean = sum(y) / actual_n
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    if ss_tot == 0:
        return 0.0

    ss_res = 0.0
    for i in range(actual_n):
        pred = sum(beta[j] * X[i][j] for j in range(p + 1))
        ss_res += (y[i] - pred) ** 2

    return max(0.0, 1.0 - ss_res / ss_tot)


def _mat_mul_transpose_first(A: list[list[float]], B: list[list[float]]) -> list[list[float]]:
    """计算 A^T @ B。"""
    rows_a = len(A)
    cols_a = len(A[0]) if A else 0
    cols_b = len(B[0]) if B else 0

    result = [[0.0] * cols_b for _ in range(cols_a)]
    for i in range(cols_a):
        for j in range(cols_b):
            s = 0.0
            for k in range(rows_a):
                s += A[k][i] * B[k][j]
            result[i][j] = s
    return result


def _mat_vec_mul_transpose(A: list[list[float]], y: list[float]) -> list[float]:
    """计算 A^T @ y。"""
    rows = len(A)
    cols = len(A[0]) if A else 0
    result = [0.0] * cols
    for i in range(cols):
        s = 0.0
        for k in range(rows):
            s += A[k][i] * y[k]
        result[i] = s
    return result


def _solve_linear_system(A: list[list[float]], b: list[float]) -> list[float] | None:
    """高斯消元求解 Ax = b。"""
    n = len(b)
    # 增广矩阵
    aug = [list(A[i]) + [b[i]] for i in range(n)]

    for col in range(n):
        # 选主元
        max_row = col
        max_val = abs(aug[col][col])
        for row in range(col + 1, n):
            if abs(aug[row][col]) > max_val:
                max_val = abs(aug[row][col])
                max_row = row
        aug[col], aug[max_row] = aug[max_row], aug[col]

        pivot = aug[col][col]
        if abs(pivot) < 1e-12:
            return None  # 奇异矩阵

        # 消元
        for row in range(col + 1, n):
            factor = aug[row][col] / pivot
            for j in range(col, n + 1):
                aug[row][j] -= factor * aug[col][j]

    # 回代
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = aug[i][n]
        for j in range(i + 1, n):
            s -= aug[i][j] * x[j]
        x[i] = s / aug[i][i]
    return x


# ---------------------------------------------------------------------------
# 因子流水线领域服务
# ---------------------------------------------------------------------------

# 上线最低评分阈值
_DEFAULT_ACTIVATE_SCORE: float = 60.0
# 检验通过最低评分阈值
_DEFAULT_VALIDATE_SCORE: float = 40.0


class FactorPipelineService:
    """因子研发流水线领域服务。

    职责:
    - 管理因子生命周期 (DISCOVERED → TESTING → VALIDATED → ACTIVE → DECAYED → RETIRED)
    - 根据检验结果自动推进/回退状态
    - 衰减监控与自动淘汰
    - 因子组合优化 (正交化、逐步回归)
    """

    def __init__(
        self,
        scorer: FactorScorer | None = None,
        decay_monitor: FactorDecayMonitor | None = None,
        activate_score: float = _DEFAULT_ACTIVATE_SCORE,
        validate_score: float = _DEFAULT_VALIDATE_SCORE,
    ) -> None:
        self._scorer = scorer or FactorScorer()
        self._decay_monitor = decay_monitor or FactorDecayMonitor()
        self._activate_score = activate_score
        self._validate_score = validate_score
        self._entries: dict[str, FactorLifecycleEntry] = {}

    # -- 注册与推进 --

    def register_factor(self, name: str, expression: str) -> FactorLifecycleEntry:
        """注册新发现的因子 (→ DISCOVERED)。"""
        if name in self._entries:
            raise ValueError(f"Factor already registered: {name}")
        entry = FactorLifecycleEntry(
            factor_name=name,
            expression=expression,
            status=FactorLifecycleStatus.DISCOVERED,
        )
        self._entries[name] = entry
        return entry

    def start_testing(self, name: str) -> FactorLifecycleEntry:
        """开始 IC/分层回测检验 (→ TESTING)。"""
        entry = self._get_entry(name)
        entry.transition_to(
            FactorLifecycleStatus.TESTING,
            reason="starting IC and layer backtest",
        )
        return entry

    def process_test_result(
        self,
        name: str,
        report: FactorTestReport,
    ) -> FactorLifecycleEntry:
        """处理检验结果，根据评分决定 VALIDATED 或回退 DISCOVERED。

        Args:
            name: 因子名。
            report: 因子测试报告。

        Returns:
            更新后的生命周期条目。
        """
        entry = self._get_entry(name)
        if entry.status != FactorLifecycleStatus.TESTING:
            raise ValueError(
                f"Factor must be in TESTING status to process results, "
                f"current: {entry.status}"
            )

        score, grade, _reasons = self._scorer.score(report)
        entry.update_metrics(
            score=score,
            grade=grade,
            ic_mean=report.ic_mean,
            ir=report.ir,
        )

        if score >= self._validate_score:
            entry.transition_to(
                FactorLifecycleStatus.VALIDATED,
                reason=f"score {score:.1f} >= {self._validate_score}, grade {grade}",
            )
            entry.validation_ic = report.ic_mean
        else:
            entry.transition_to(
                FactorLifecycleStatus.DISCOVERED,
                reason=f"score {score:.1f} < {self._validate_score}, grade {grade}",
            )

        return entry

    def activate_factor(self, name: str) -> FactorLifecycleEntry:
        """激活因子 (VALIDATED → ACTIVE)。

        只有评分达到激活阈值的因子才能上线。
        """
        entry = self._get_entry(name)
        if entry.status != FactorLifecycleStatus.VALIDATED:
            raise ValueError(
                f"Factor must be VALIDATED to activate, current: {entry.status}"
            )
        if entry.score < self._activate_score:
            raise ValueError(
                f"Factor score {entry.score:.1f} < activate threshold {self._activate_score}"
            )
        entry.transition_to(
            FactorLifecycleStatus.ACTIVE,
            reason=f"activated with score {entry.score:.1f}, grade {entry.grade}",
        )
        return entry

    # -- 衰减监控 --

    def check_decay(self, name: str, current_ic_mean: float) -> DecayCheckResult:
        """检查因子是否衰减，自动更新状态。

        ACTIVE 因子: 若衰减 → DECAYED。
        DECAYED 因子: 连续衰减达标 → RETIRED。

        Args:
            name: 因子名。
            current_ic_mean: 最近周期的 IC 均值。

        Returns:
            衰减检查结果。
        """
        entry = self._get_entry(name)
        if entry.status not in (FactorLifecycleStatus.ACTIVE, FactorLifecycleStatus.DECAYED):
            raise ValueError(
                f"Can only check decay for ACTIVE/DECAYED factors, current: {entry.status}"
            )

        result = self._decay_monitor.check_decay(entry, current_ic_mean)
        entry.decay_count = result.decay_count

        if result.is_decayed:
            if entry.status == FactorLifecycleStatus.ACTIVE:
                entry.transition_to(
                    FactorLifecycleStatus.DECAYED,
                    reason=f"IC decay: ratio={result.ic_ratio:.2f}",
                )
            elif entry.status == FactorLifecycleStatus.DECAYED:
                if self._decay_monitor.should_retire(entry):
                    entry.transition_to(
                        FactorLifecycleStatus.RETIRED,
                        reason=f"auto-retired after {entry.decay_count} consecutive decays",
                    )
        else:
            # IC 恢复，重置衰减计数
            entry.decay_count = 0
            if entry.status == FactorLifecycleStatus.DECAYED:
                entry.transition_to(
                    FactorLifecycleStatus.ACTIVE,
                    reason=f"IC recovered: ratio={result.ic_ratio:.2f}",
                )

        return result

    def revalidate_factor(self, name: str) -> FactorLifecycleEntry:
        """重新验证衰减因子 (DECAYED → TESTING)。"""
        entry = self._get_entry(name)
        entry.transition_to(
            FactorLifecycleStatus.TESTING,
            reason="re-validation after decay",
        )
        return entry

    # -- 手动操作 --

    def retire_factor(self, name: str, reason: str = "manual retire") -> FactorLifecycleEntry:
        """手动退役因子。"""
        entry = self._get_entry(name)
        entry.transition_to(FactorLifecycleStatus.RETIRED, reason=reason)
        return entry

    # -- 批量衰减检查 --

    def batch_check_decay(
        self,
        ic_by_factor: dict[str, float],
    ) -> list[DecayCheckResult]:
        """批量检查所有 ACTIVE/DECAYED 因子的衰减情况。

        Args:
            ic_by_factor: {因子名: 最近 IC 均值}。

        Returns:
            衰减检查结果列表。
        """
        results: list[DecayCheckResult] = []
        for name, ic in ic_by_factor.items():
            entry = self._entries.get(name)
            if entry is None:
                continue
            if entry.status in (FactorLifecycleStatus.ACTIVE, FactorLifecycleStatus.DECAYED):
                results.append(self.check_decay(name, ic))
        return results

    # -- 因子组合优化 --

    @staticmethod
    def orthogonalize_factors(
        factor_matrix: list[list[float]],
    ) -> list[list[float]]:
        """因子正交化 (Gram-Schmidt)。"""
        return FactorCombiner.orthogonalize(factor_matrix)

    @staticmethod
    def select_factors(
        factor_values: list[dict[str, float]],
        target_values: list[float],
        factor_names: list[str],
        max_factors: int | None = None,
    ) -> list[str]:
        """逐步回归选择因子。"""
        return FactorCombiner.stepwise_select(
            factor_values=factor_values,
            target_values=target_values,
            factor_names=factor_names,
            max_factors=max_factors,
        )

    # -- 查询 --

    def get_entry(self, name: str) -> FactorLifecycleEntry | None:
        """获取因子生命周期条目（不抛异常）。"""
        return self._entries.get(name)

    def get_entries_by_status(
        self,
        status: FactorLifecycleStatus,
    ) -> list[FactorLifecycleEntry]:
        """按状态筛选条目。"""
        return [e for e in self._entries.values() if e.status == status]

    def get_active_factors(self) -> list[FactorLifecycleEntry]:
        """获取所有活跃因子。"""
        return self.get_entries_by_status(FactorLifecycleStatus.ACTIVE)

    def get_summary(self) -> dict[str, object]:
        """获取因子生命周期汇总。"""
        by_status: dict[str, int] = {}
        for entry in self._entries.values():
            by_status[entry.status] = by_status.get(entry.status, 0) + 1
        return {
            "total": len(self._entries),
            "by_status": by_status,
        }

    # -- 内部 --

    def _get_entry(self, name: str) -> FactorLifecycleEntry:
        """获取条目，不存在则抛 KeyError。"""
        entry = self._entries.get(name)
        if entry is None:
            raise KeyError(f"Factor not in pipeline: {name}")
        return entry
